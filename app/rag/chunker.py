"""
Context-Aware Document Chunker for Maternal Health RAG Pipeline
---------------------------------------------------------------
Chunks documents by section boundaries (not token count) and enriches
each chunk with metadata for better retrieval.

Strategy:
1. Parse document metadata (source, topic, license)
2. Split on ## headers to create section-level chunks
3. For sections with ### subsections, keep them grouped under their parent
4. Extract the Clinical Language Guide and attach relevant entries to parent chunks
5. Flag EMERGENCY/IMPORTANT/CRISIS content for priority retrieval
6. Include document intro context in each chunk for grounding
"""

import os
import re
import hashlib


def parse_metadata(text):
    """Extract the metadata header from the top of the document."""
    metadata = {}
    lines = text.strip().split('\n')

    for line in lines:
        if line.startswith('Source:'):
            metadata['source'] = line.replace('Source:', '').strip()
        elif line.startswith('License:'):
            metadata['license'] = line.replace('License:', '').strip()
        elif line.startswith('Topic:'):
            metadata['topic'] = line.replace('Topic:', '').strip()
        elif line.startswith('#'):
            break

    return metadata


def extract_document_title(text):
    """Get the # level title."""
    match = re.search(r'^# (.+)$', text, re.MULTILINE)
    return match.group(1).strip() if match else "Unknown"


def extract_intro(text):
    """Get the text between the # title and the first ## section."""
    title_match = re.search(r'^# .+$', text, re.MULTILINE)
    if not title_match:
        return ""

    after_title = text[title_match.end():].strip()

    first_section = re.search(r'^## ', after_title, re.MULTILINE)
    if not first_section:
        return after_title

    return after_title[:first_section.start()].strip()


def parse_clinical_language_guide(text):
    """
    Extract the Clinical Language Guide section and parse each mapping.
    Returns a list of mappings and the full guide text.
    """
    clg_match = re.search(r'## Clinical Language Guide\n(.+?)(?=\n## |\Z)', text, re.DOTALL)
    if not clg_match:
        return [], ""

    clg_text = clg_match.group(0)

    mappings = []
    for line in clg_text.split('\n'):
        if '→' in line or '→' in line:
            line_clean = line.strip().lstrip('- ')
            mappings.append(line_clean)

    return mappings, clg_text


def match_clinical_guides_to_section(section_text, clinical_mappings):
    """
    Match Clinical Language Guide entries to a section based on keyword overlap.
    Checks BOTH sides of the arrow (patient language AND clinical terms)
    so we catch matches like "constipation" appearing in the clinical side
    even when the patient phrase says "can't go to the bathroom".
    """
    matched = []
    section_lower = section_text.lower()

    stop_words = {
        'feel', 'like', 'have', 'been', 'really', 'keep', 'just',
        'that', 'this', 'with', 'from', 'about', 'your', 'much',
        'more', 'some', 'very', 'when', 'what', 'experiencing',
        'discuss', 'would', 'concerned', 'having', 'need', 'help',
        'related', 'including', 'describe', 'support', 'possible',
        'indicate', 'pregnancy', 'pregnant', 'during', 'provider',
        'baby', 'currently', 'taking', 'history', 'previous',
        'before', 'after', 'might', 'could', 'should', 'also',
        'safe', 'safety', 'consider', 'additional', 'monitoring',
        'management', 'options', 'condition', 'complications',
        'interested', 'confirmation', 'alternatives', 'concerns',
        'treatment', 'reduction', 'considerations'
    }

    for mapping in clinical_mappings:
        full_mapping_lower = mapping.lower()

        keywords = re.findall(r'\b\w{4,}\b', full_mapping_lower)
        keywords = [k for k in keywords if k not in stop_words]

        match_count = sum(1 for k in keywords if k in section_lower)

        if match_count >= 1:
            matched.append(mapping)

    return matched


def extract_alerts(text):
    """Find EMERGENCY, IMPORTANT, and CRISIS callouts in text."""
    alerts = []

    for alert_type in ['EMERGENCY', 'IMPORTANT', 'CRISIS']:
        pattern = rf'{alert_type}:\s*(.+?)(?=\n\n|\n##|\Z)'
        matches = re.findall(pattern, text, re.DOTALL)
        for match in matches:
            alerts.append({
                'type': alert_type.lower(),
                'content': match.strip()
            })

    return alerts


def split_into_sections(text):
    """
    Split document into sections based on ## headers.
    Keeps ### subsections grouped under their parent ##.
    Excludes the Clinical Language Guide section (handled separately).
    """
    sections = []

    pattern = r'^## (?!#)'
    parts = re.split(pattern, text, flags=re.MULTILINE)

    headers = re.findall(r'^## (?!#)(.+)$', text, re.MULTILINE)

    for i, header in enumerate(headers):
        header_clean = header.strip()

        if 'Clinical Language Guide' in header_clean:
            continue

        if i + 1 < len(parts):
            content = parts[i + 1].strip()

            sections.append({
                'header': header_clean,
                'content': content,
                'alerts': extract_alerts(content)
            })

    return sections


def generate_chunk_id(filename, section_header):
    """Generate a deterministic chunk ID."""
    raw = f"{filename}::{section_header}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def chunk_document(filepath):
    """
    Process a single document into context-rich chunks.

    Each chunk contains:
    - id: unique identifier
    - text: the actual content to embed
    - metadata: rich metadata for filtering and context
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        text = f.read()

    filename = os.path.basename(filepath)
    metadata = parse_metadata(text)
    title = extract_document_title(text)
    intro = extract_intro(text)
    clinical_mappings, clinical_guide_full = parse_clinical_language_guide(text)
    sections = split_into_sections(text)

    chunks = []

    for section in sections:
        matched_guides = match_clinical_guides_to_section(
            section['content'], clinical_mappings
        )

        chunk_text_parts = []

        chunk_text_parts.append(f"Topic: {metadata.get('topic', title)}")
        chunk_text_parts.append(f"Section: {section['header']}")
        chunk_text_parts.append("")

        if intro:
            first_sentence = intro.split('.')[0] + '.'
            chunk_text_parts.append(f"Context: {first_sentence}")
            chunk_text_parts.append("")

        chunk_text_parts.append(section['content'])

        if matched_guides:
            chunk_text_parts.append("")
            chunk_text_parts.append("Communication Guide:")
            for guide in matched_guides:
                chunk_text_parts.append(f"  {guide}")

        chunk_text = '\n'.join(chunk_text_parts)

        has_emergency = any(a['type'] == 'emergency' for a in section['alerts'])
        has_important = any(a['type'] == 'important' for a in section['alerts'])
        has_crisis = any(a['type'] == 'crisis' for a in section['alerts'])

        chunk = {
            'id': generate_chunk_id(filename, section['header']),
            'text': chunk_text,
            'metadata': {
                'source_file': filename,
                'source': metadata.get('source', ''),
                'license': metadata.get('license', ''),
                'document_topic': metadata.get('topic', title),
                'document_title': title,
                'section_header': section['header'],
                'has_emergency_info': has_emergency,
                'has_important_info': has_important,
                'has_crisis_info': has_crisis,
                'priority': 'high' if (has_emergency or has_crisis) else 'normal',
                'clinical_guides_count': len(matched_guides),
                'char_count': len(chunk_text),
            }
        }

        chunks.append(chunk)

    if clinical_mappings:
        guide_text_parts = [
            f"Topic: {metadata.get('topic', title)}",
            "Section: Clinical Language Guide",
            "",
            "This guide helps patients communicate symptoms to their healthcare provider using clinical terminology:",
            ""
        ]
        for mapping in clinical_mappings:
            guide_text_parts.append(f"  {mapping}")

        chunks.append({
            'id': generate_chunk_id(filename, 'Clinical Language Guide'),
            'text': '\n'.join(guide_text_parts),
            'metadata': {
                'source_file': filename,
                'source': metadata.get('source', ''),
                'license': metadata.get('license', ''),
                'document_topic': metadata.get('topic', title),
                'document_title': title,
                'section_header': 'Clinical Language Guide',
                'has_emergency_info': False,
                'has_important_info': False,
                'has_crisis_info': False,
                'priority': 'normal',
                'clinical_guides_count': len(clinical_mappings),
                'char_count': len('\n'.join(guide_text_parts)),
            }
        })

    return chunks
