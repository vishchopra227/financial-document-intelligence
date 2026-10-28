"""Financial-aware chunking engine with page attribution and table boundary preservation."""

import re
import uuid
from typing import List, Optional
from pydantic import BaseModel, Field

from backend.app.services.ingestion.parser import ExtractedDocument, ExtractedPage


class DocumentChunk(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    chunk_index: int
    content: str
    char_count: int
    has_table: bool = False
    metadata: dict = Field(default_factory=dict)


class FinancialChunker:
    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, doc_id: str, extracted_doc: ExtractedDocument) -> List[DocumentChunk]:
        """Split an ExtractedDocument into page-attributed chunks.
        Never splits across table blocks and keeps financial figures intact.
        """
        all_chunks: List[DocumentChunk] = []
        global_chunk_idx = 0

        for page in extracted_doc.pages:
            page_text = page.text.strip()
            if not page_text:
                continue

            page_chunks = self._chunk_page(
                text=page_text,
                page_num=page.page_number,
                doc_id=doc_id,
                filename=extracted_doc.filename,
                start_chunk_idx=global_chunk_idx,
            )
            all_chunks.extend(page_chunks)
            global_chunk_idx += len(page_chunks)

        return all_chunks

    def _chunk_page(
        self,
        text: str,
        page_num: int,
        doc_id: str,
        filename: str,
        start_chunk_idx: int,
    ) -> List[DocumentChunk]:
        """Chunk a single page, treating table blocks atomically."""
        chunks: List[DocumentChunk] = []
        
        # Protect table blocks: [TABLE START] ... [TABLE END]
        table_pattern = re.compile(r"(\[TABLE START\].*?\[TABLE END\])", re.DOTALL)
        segments = table_pattern.split(text)

        current_buffer = ""
        current_has_table = False

        for segment in segments:
            if not segment.strip():
                continue

            is_table = segment.strip().startswith("[TABLE START]") and segment.strip().endswith("[TABLE END]")

            if is_table:
                # If current buffer has text, flush it before the table
                if current_buffer.strip():
                    chunks.append(self._create_chunk(
                        content=current_buffer.strip(),
                        page_num=page_num,
                        doc_id=doc_id,
                        filename=filename,
                        chunk_idx=start_chunk_idx + len(chunks),
                        has_table=current_has_table,
                    ))
                    current_buffer = ""
                    current_has_table = False

                # If table is smaller than 2x chunk size, keep it whole
                if len(segment) <= self.chunk_size * 2:
                    chunks.append(self._create_chunk(
                        content=segment.strip(),
                        page_num=page_num,
                        doc_id=doc_id,
                        filename=filename,
                        chunk_idx=start_chunk_idx + len(chunks),
                        has_table=True,
                    ))
                else:
                    # Very large table: split by table rows (\n)
                    sub_chunks = self._split_text_by_delimiter(segment, delimiter="\n")
                    for sub in sub_chunks:
                        chunks.append(self._create_chunk(
                            content=sub.strip(),
                            page_num=page_num,
                            doc_id=doc_id,
                            filename=filename,
                            chunk_idx=start_chunk_idx + len(chunks),
                            has_table=True,
                        ))
                continue

            # Standard narrative text: split by paragraphs (\n\n) or sentences
            paragraphs = segment.split("\n\n")
            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                if len(current_buffer) + len(para) + 2 <= self.chunk_size:
                    current_buffer += ("\n\n" if current_buffer else "") + para
                else:
                    # If current buffer already has meaningful content, flush it
                    if len(current_buffer) >= self.chunk_size - self.chunk_overlap:
                        chunks.append(self._create_chunk(
                            content=current_buffer.strip(),
                            page_num=page_num,
                            doc_id=doc_id,
                            filename=filename,
                            chunk_idx=start_chunk_idx + len(chunks),
                            has_table=current_has_table,
                        ))
                        # Keep overlap from the end of current_buffer
                        overlap_start = max(0, len(current_buffer) - self.chunk_overlap)
                        current_buffer = current_buffer[overlap_start:].strip() + "\n\n" + para
                    else:
                        current_buffer += ("\n\n" if current_buffer else "") + para

                    # If paragraph itself is larger than chunk_size, split by sentences
                    while len(current_buffer) > self.chunk_size:
                        split_idx = self._find_split_point(current_buffer, self.chunk_size)
                        chunk_part = current_buffer[:split_idx].strip()
                        if chunk_part:
                            chunks.append(self._create_chunk(
                                content=chunk_part,
                                page_num=page_num,
                                doc_id=doc_id,
                                filename=filename,
                                chunk_idx=start_chunk_idx + len(chunks),
                                has_table=current_has_table,
                            ))
                        overlap_start = max(0, split_idx - self.chunk_overlap)
                        current_buffer = current_buffer[overlap_start:].strip()

        if current_buffer.strip():
            chunks.append(self._create_chunk(
                content=current_buffer.strip(),
                page_num=page_num,
                doc_id=doc_id,
                filename=filename,
                chunk_idx=start_chunk_idx + len(chunks),
                has_table=current_has_table,
            ))

        return chunks

    def _find_split_point(self, text: str, max_pos: int) -> int:
        """Find natural sentence or clause boundary within limit."""
        if len(text) <= max_pos:
            return len(text)

        search_window = text[max(0, max_pos - 150):max_pos]
        # Look for sentence endings
        match = re.search(r"(\.|\?|!|\n)\s+[A-Z0-9]", search_window)
        if match:
            return max(0, max_pos - 150) + match.start() + 1

        # Fallback to last whitespace
        last_space = text.rfind(" ", 0, max_pos)
        if last_space > max_pos // 2:
            return last_space

        return max_pos

    def _split_text_by_delimiter(self, text: str, delimiter: str = "\n") -> List[str]:
        """Split text while respecting chunk size on delimiter boundaries."""
        lines = text.split(delimiter)
        result = []
        buf = []
        buf_len = 0

        for line in lines:
            line_len = len(line) + len(delimiter)
            if buf_len + line_len > self.chunk_size and buf:
                result.append(delimiter.join(buf))
                buf = [line]
                buf_len = line_len
            else:
                buf.append(line)
                buf_len += line_len

        if buf:
            result.append(delimiter.join(buf))
        return result

    def _create_chunk(
        self,
        content: str,
        page_num: int,
        doc_id: str,
        filename: str,
        chunk_idx: int,
        has_table: bool,
    ) -> DocumentChunk:
        return DocumentChunk(
            chunk_id=f"{doc_id}_p{page_num}_c{chunk_idx}",
            document_id=doc_id,
            filename=filename,
            page_number=page_num,
            chunk_index=chunk_idx,
            content=content,
            char_count=len(content),
            has_table=has_table,
            metadata={
                "document_id": doc_id,
                "filename": filename,
                "page_number": page_num,
                "chunk_index": chunk_idx,
            },
        )
