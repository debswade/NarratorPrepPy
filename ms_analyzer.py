# ms_analyzer.py

import requests
import pdfplumber
import tempfile
import re
import os
import pandas as pd
import logging
# from text_utils import extract_text_by_page, count_words, split_chapters

def download_pdf(url):
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to download: {response.status_code}")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    tmp.write(response.content)
    tmp.close()
    return tmp.name

def extract_text_by_page(pdf_path):
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text()
            if isinstance(text, str):
                pages.append(text)
            else:
                print(f"⚠️ Skipping non-string page {page_num + 1}")
                pages.append("")  # Include empty string to preserve indexing
    return pages

def count_words(text):
    import re
    return len(re.findall(r'\b\w+\b', text))

def split_chapters(pages):

    chapter_regex = re.compile(r"^(?:chapter|book)\s+(?:\d+|[a-z]+|[ivxlcdm]+)\b.*", re.IGNORECASE)
    section_patterns = {
        "Prologue": re.compile(r"^prologue\b", re.IGNORECASE),
        "Epilogue": re.compile(r"^epilogue\b", re.IGNORECASE),
        "Acknowledgements": re.compile(r"^acknowledg(e)?ments\b", re.IGNORECASE),
        "Dedication": re.compile(r"^dedication\b", re.IGNORECASE),
        "Character List": re.compile(r"^character list\b", re.IGNORECASE),
        "About the Author": re.compile(r"^about the author\b", re.IGNORECASE),
        "Also by the Author": re.compile(r"^also by the author\b", re.IGNORECASE),
        "Thank You": re.compile(r"^thank you\b", re.IGNORECASE),
    }

    chapters = []
    current_chapter = []
    current_title = None
    current_start = None

    for i, page_text in enumerate(pages):
        if not isinstance(page_text, str):
            print(f"⚠️ Skipping non-string page {i + 1}")
            continue

        lines = page_text.splitlines()
        matched = False

        for line in lines:
            clean_line = line.strip()

            # Match chapter heading
            if chapter_regex.match(clean_line):
                matched = True
                if current_chapter:
                    chapters.append((current_title, current_start, i - 1, current_chapter))
                current_title = clean_line
                current_start = i
                current_chapter = [(i, page_text)]
                break

            # Match other common section titles
            for label, regex in section_patterns.items():
                if regex.match(clean_line):
                    matched = True
                    if current_chapter:
                        chapters.append((current_title, current_start, i - 1, current_chapter))
                    current_title = label
                    current_start = i
                    current_chapter = [(i, page_text)]
                    break

            if matched:
                break

        if not matched and current_chapter is not None:
            current_chapter.append((i, page_text))

    if current_chapter:
        chapters.append((current_title, current_start, len(pages) - 1, current_chapter))

    return chapters

def get_chapter_start_pages(chapters, pages):
    start_pages = {}

    for chapter in chapters:
        # First text chunk of chapter
        first_entry = chapter[0]
        if isinstance(first_entry, tuple):
            page_index, page_text = first_entry
            # Try to get chapter heading from first 2 lines
            possible_title = page_text.strip().splitlines()[0].strip().upper()

        else:
            continue  # skip broken chapter entries

        print(f"🔍 Searching for chapter title: '{possible_title}'")

        for i, page in enumerate(pages):
            if possible_title in page.upper():
                start_pages[possible_title] = i + 1
                break
        else:
            start_pages[possible_title] = None  # not found

    return start_pages


def analyze(pdf_path_or_url):
    # Handle remote URL: download to a temporary file
    if pdf_path_or_url.startswith("http://") or pdf_path_or_url.startswith("https://"):
        response = requests.get(pdf_path_or_url)
        if response.status_code != 200:
            raise ValueError("Failed to download the file.")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(response.content)
            pdf_path = tmp_file.name
    else:
        pdf_path = pdf_path_or_url

    print("📄 Extracting text...")
    pages = extract_text_by_page(pdf_path)

    print("📚 Splitting chapters...")
    chapters = split_chapters(pages)

    print("📊 Analyzing structure...\n")
    chapter_data = []

    for i, (title, start_page, end_page, content) in enumerate(chapters, start=1):
        try:
            text_block = "\n".join(
                line for entry in content if entry and isinstance(entry, tuple) for _, line in [entry]
            )
            word_count = count_words(text_block)
            page_count = end_page - start_page + 1

            chapter_data.append({
                "chapter": i,
                "title": title,
                "start_page": start_page + 1,  # convert to 1-based page numbers
                "end_page": end_page + 1,
                "page_count": page_count,
                "word_count": word_count,
            })
        except Exception as e:
            print(f"❌ Error processing chapter {i}: {e}")
            chapter_data.append({
                "chapter": i,
                "title": title,
                "start_page": "?",
                "end_page": "?",
                "page_count": "?",
                "word_count": 0,
            })

    stats = {
        "chapter_count": len(chapter_data),
    }

    return stats, chapter_data

if __name__ == '__main__':
    logging.getLogger("pdfminer").setLevel(logging.ERROR)

    # Either provide a URL or a local file path here
    input_path = input("Enter PDF URL or local file path: ").strip()

    # Fallback for testing (you can comment this out when running normally)
    if not input_path:
        # Example Google Drive URL:
        # input_path = "https://drive.google.com/file/d/1LI5qYJmzo6aVWPfynYadnwj_fpeXhKm3/view?usp=drive_link"
        input_path = "/Users/debsbalm/PyCharmProjects/NarratorPrepPy/TheSundering.pdf"

    stats, breakdown = analyze(input_path)
    table = pd.DataFrame(breakdown)

    print("\n📈 Document Stats:\n", stats)
    print("\n📖 Chapter Breakdown:\n", table.to_string(index=False))
