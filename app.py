from flask import Flask, request, send_file, render_template, redirect, url_for, Response, stream_with_context
import requests
import string
import os
import re
from io import BytesIO
from time import sleep

# gtts booted me...
#from gtts import gTTS

# tts is very finicky
from TTS.api import TTS
import soundfile as sf

# kittens?
#import numpy as np
#from kittentts import KittenTTS
#kittenstts = KittenTTS("KittenML/kitten-tts-nano-0.2")
#import soundfile as sf


tts_coqui = TTS(model_name="tts_models/en/ljspeech/speedy-speech", progress_bar=False)
#tts_coqui = TTS(model_name="tts_models/en/ljspeech/glow-tts", progress_bar=False)

app = Flask(__name__)

CHAPTER_LENGTH = 10000
STREAMING_CHARS = 100
RECENT_BOOKS = []

# store the whole book in global? Seems dumb?
CURRENT_BOOK_CHAPTERS = []
        
default_sound = tts_coqui.tts('Cough cough excuse me excuse me')


def clean_gutenberg_text(text):
    # clean text maybe

    text = text.replace('\r\n', '\n')

    # Convert multiple blank lines to a single blank line
    text = re.sub(r'\n\s*\n', '\n\n', text)

    # Replace single newlines (inside paragraphs) with a space
    text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)
    text = re.sub(r' +', ' ', text)  # multiple spaces → single space
    text = re.sub(r'_', '', text)  # no underscores

    allowed_chars = string.ascii_letters + string.digits + string.punctuation + ' \n\t'
    text = ''.join(c for c in text if c in allowed_chars)

    text = text.strip()

    start = re.search(r"\*\*\* START OF.*?\*\*\*", text)
    end = re.search(r"\*\*\* END OF.*?\*\*\*", text)
    if start and end:
        return text[start.end():end.start()]
    else:
        return text

def section_text(text, mode = "paragraph", max_chars=CHAPTER_LENGTH):
    """
    Split Gutenberg text into sentences or paragraphs.

    Args:
        text (str): Raw text from Gutenberg.
        mode (str): "sentence" or "paragraph".

    Returns:
        list of str: Cleaned sentences or paragraphs.
    """

    # Choose regex based on mode
    if mode == "paragraph":
        # Paragraphs split by double newline
        split_pattern = r'\n\n+'
    elif mode == "sentence":
        # Sentences split by ., !, ?, or newline
        split_pattern = r'(?<=[.!?\n])+'
    else:
        raise ValueError("mode must be 'sentence' or 'paragraph'")

    sections = []
    current = ""

    for block in re.split(split_pattern, text):
        if len(current) + len(block) < max_chars:
            current += block + ' '
        elif len(current)<=10:
            current += block + ' '
        else:
            sections.append(current.strip())
            current = block + ' '

    if current.strip():
        sections.append(current.strip())

    return sections

@app.route("/audio/<int:sentence_id>")
def serve_sentence(sentence_id):
    fp = BytesIO()
    try:
        tts = tts_coqui.tts(CURRENT_BOOK_CHAPTERS[sentence_id-1])
        sf.write(fp, tts, tts_coqui.synthesizer.output_sample_rate, format='MP3') #WAV')
        fp.seek(0)
        return send_file(fp, mimetype="audio/mpeg") #wav")
    except:
        sf.write(fp, default_sound, tts_coqui.synthesizer.output_sample_rate, format='MP3') #WAV')
        fp.seek(0)
        return send_file(fp, mimetype="audio/mpeg") #wav")

@app.route('/')
def index():
    return render_template("index.html", recent_books = RECENT_BOOKS)

@app.route("/search")
def search():
    query = request.args.get("query")
    if not query:
        return "Please provide a search query", 400

    url = f"https://gutendex.com/books/?search={query}"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()

    # Extract first 10 books
    books = []
    for b in data["results"][:10]:
        #print(b)
        title = b["title"]
        authors = ", ".join(a["name"] for a in b["authors"])
        txt_url = b["formats"].get("text/plain; charset=utf-8") or b["formats"].get("text/plain") or b["formats"].get("text/plain; charset=us-ascii")
        if txt_url:
            books.append({"title": title, "authors": authors, "url": txt_url})

    return render_template("search_results.html", books=books)

@app.route('/analyse', methods=['POST'])
def analyse():
    book_url = request.form['book_url']
    title = request.form['title']
    authors = request.form['authors']

    # save this book to the recently viewed book list
    global RECENT_BOOKS
    book_info = {"book_url": book_url, "title": title, "authors": authors}
    if book_info not in RECENT_BOOKS:
        RECENT_BOOKS.append(book_info)
        # keep only last 5 books
        RECENT_BOOKS = RECENT_BOOKS[-5:]

    return redirect(url_for("show_book", book_url = book_url, title = title, authors = authors))

@app.route('/book')
def show_book():
    book_url = request.args.get('book_url')
    title = request.args.get('title')
    authors = request.args.get('authors')
    
    # Fetch book text
    resp = requests.get(book_url)
    resp.raise_for_status()

    sections = section_text(clean_gutenberg_text(resp.text), mode = "sentence", max_chars=STREAMING_CHARS)

    global CURRENT_BOOK_CHAPTERS
    CURRENT_BOOK_CHAPTERS = sections

    section_meta = [
        {"index": i + 1, 
            "text":s
            }
        for i, s in enumerate(sections)
    ]

    return render_template(
        "show_book.html",
        book_url=book_url,
        title=title,
        authors=authors,
        sections=section_meta
    )

if __name__ == "__main__":
    app.run(debug=True)

