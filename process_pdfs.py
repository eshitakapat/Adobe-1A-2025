

import fitz
import json
import os
import re
from collections import defaultdict, Counter

def t(x): return ' '.join(x.strip().split())
def ae(a, b, d=0.5): return abs(a - b) <= d

def fs_level(s, ths):
    for i, th in enumerate(ths):
        if ae(s, th): return f"H{i+1}"
    return "Body"

def extract_text_with_metadata(doc_path):
    doc = fitz.open(doc_path)
    spans_data = []
    for page_num in range(doc.page_count):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = t(span["text"])
                    if not text: continue
                    spans_data.append({
                        "text": text,
                        "x0": span["bbox"][0],
                        "y0": span["bbox"][1],
                        "x1": span["bbox"][2],
                        "y1": span["bbox"][3],
                        "size": round(span["size"], 1),
                        "page": page_num
                    })
    return spans_data

def identify_document_title(spans_data):
    first_page_spans = [s for s in spans_data if s['page'] == 0]
    if not first_page_spans: return "Untitled Document"
    max_font_size = max(s['size'] for s in first_page_spans)
    potential_spans = sorted(
        [s for s in first_page_spans if ae(s['size'], max_font_size, d=1.0) and s['y0'] < 300],
        key=lambda s: (s['y0'], s['x0'])
    )
    title_candidates = []
    current_line = []
    last_y0 = -1
    for span in potential_spans:
        if current_line and abs(span['y0'] - last_y0) > 5:
            sorted_line = sorted(current_line, key=lambda s: s['x0'])
            title_candidates.append(t(" ".join([s['text'] for s in sorted_line])))
            current_line = []
        current_line.append(span)
        last_y0 = span['y0']
    if current_line:
        sorted_line = sorted(current_line, key=lambda s: s['x0'])
        title_candidates.append(t(" ".join([s['text'] for s in sorted_line])))
    unique_title_lines = []
    for line in title_candidates:
        if line and line not in unique_title_lines and len(unique_title_lines) < 4:
            if line.lower().strip() not in ["", "document", "report", "contents", "table of contents"] and len(line) > 5:
                unique_title_lines.append(line)
    return "  ".join(unique_title_lines).strip() if unique_title_lines else "Untitled Document"

def infer_heading_thresholds(spans_data):
    font_size_counts = Counter(s['size'] for s in spans_data)
    body_size = font_size_counts.most_common(1)[0][0]
    filtered_sizes = {s: count for s, count in font_size_counts.items() if s >= 9.0}
    sorted_sizes = sorted(filtered_sizes.keys(), reverse=True)
    thresholds = []
    for size in sorted_sizes:
        if size > body_size + 0.9:
            if not any(ae(size, th, d=0.5) for th in thresholds):
                thresholds.append(size)
        if len(thresholds) >= 3:
            break
    thresholds.append(body_size)
    return sorted(thresholds, reverse=True)

def find_true_page_for_heading(text, spans_data):
    cleaned = re.sub(r'\s+', ' ', text).lower().strip()
    best_match = None
    for s in spans_data:
        candidate = re.sub(r'\s+', ' ', s['text']).lower().strip()
        if cleaned.startswith(candidate) or candidate.startswith(cleaned):
            if not best_match or s['page'] < best_match['page']:
                best_match = s
    return best_match['page'] + 1 if best_match else 1

def extract_outline(spans_data, heading_thresholds):
    outline = []
    seen_texts = set()
    spans_data.sort(key=lambda s: (s['page'], s['y0'], s['x0']))
    grouped_lines = []
    current_line_spans = []
    last_y_pos = -1
    last_page = -1
    for s in spans_data:
        if s['page'] != last_page or (current_line_spans and abs(s['y0'] - last_y_pos) > 5):
            if current_line_spans:
                merged_text = t(" ".join([cs['text'] for cs in current_line_spans]))
                avg_size = sum(cs['size'] for cs in current_line_spans) / len(current_line_spans)
                grouped_lines.append({
                    "text": merged_text,
                    "size": avg_size,
                    "page": current_line_spans[0]['page'],
                    "y0": current_line_spans[0]['y0'],
                    "x0": current_line_spans[0]['x0']
                })
            current_line_spans = [s]
            last_page = s['page']
        else:
            current_line_spans.append(s)
        last_y_pos = s['y0']
    if current_line_spans:
        merged_text = t(" ".join([cs['text'] for cs in current_line_spans]))
        avg_size = sum(cs['size'] for cs in current_line_spans) / len(current_line_spans)
        grouped_lines.append({
            "text": merged_text,
            "size": avg_size,
            "page": current_line_spans[0]['page'],
            "y0": current_line_spans[0]['y0'],
            "x0": current_line_spans[0]['x0']
        })

    merged_grouped_lines = []
    i = 0
    while i < len(grouped_lines):
        current = grouped_lines[i]
        if i + 1 < len(grouped_lines):
            next_line = grouped_lines[i + 1]
            if re.match(r'.*\b(–|-)$', current['text']) or current['text'].endswith("Extension"):
                merged_text = t(current['text'] + " " + next_line['text'])
                avg_size = (current['size'] + next_line['size']) / 2
                merged_grouped_lines.append({
                    "text": merged_text,
                    "size": avg_size,
                    "page": current['page'],
                    "y0": current['y0'],
                    "x0": current['x0']
                })
                i += 2
                continue
        merged_grouped_lines.append(current)
        i += 1

    for line_data in merged_grouped_lines:
        text = line_data['text']
        font_size = line_data['size']
        if len(text) < 4 or text.isdigit():
            continue
        if len(text) > 120 or text[0].islower():
            continue
        level = fs_level(font_size, heading_thresholds)
        if level != "Body" and re.match(r'^(\d+(\.\d+)*\s+|[A-Z])', text.strip()):
            formatted_text = text.strip()
            if not formatted_text.endswith(('.', '!', '?', ':', ';', ',')):
                formatted_text += " "
            if formatted_text not in seen_texts and "...." not in formatted_text and not re.search(r'\d+\s*$', formatted_text):
                outline.append({
                    "level": level,
                    "text": formatted_text,
                    "page": find_true_page_for_heading(formatted_text, spans_data)
                })
                seen_texts.add(formatted_text)
    return outline

def process_pdf(fp):
    spans_data = extract_text_with_metadata(fp)
    title = identify_document_title(spans_data)
    inferred_ths = infer_heading_thresholds(spans_data)
    if not inferred_ths:
        inferred_ths = [24.0, 16.0, 12.0, 10.0]
    outline = extract_outline(spans_data, inferred_ths)
    all_unique_sizes = sorted(list(set(s['size'] for s in spans_data)), reverse=True)
    return {"title": title, "outline": outline, "fontSizes": all_unique_sizes}

def run_all_pdfs(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".pdf"):
            pdf_path = os.path.join(input_dir, filename)
            try:
                result = process_pdf(pdf_path)
                output_json_path = os.path.join(output_dir, filename.replace(".pdf", ".json"))
                with open(output_json_path, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    input_directory = "sample_dataset/pdfs"
    output_directory = "sample_dataset/outputs"
    run_all_pdfs(input_directory, output_directory)
