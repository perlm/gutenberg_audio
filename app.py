from flask import Flask, request, send_file, render_template, redirect, url_for
import requests
from gtts import gTTS
import os
import re

app = Flask(__name__)

AUDIO_DIR = "audio"
MAX_CHARS = 4000  # gTTS-safe section size
RECENT_BOOKS = []

def clean_gutenberg_text(text):
    start = re.search(r"\*\*\* START OF.*?\*\*\*", text)
    end = re.search(r"\*\*\* END OF.*?\*\*\*", text)

    if start and end:
        return text[start.end():end.start()]
    else:
        return text

def section_text(text, max_chars=MAX_CHARS):
    """Split text into sections without cutting sentences."""
    sections = []
    current = ""

    for paragraph in text.split("\n"):
        if len(current) + len(paragraph) < max_chars:
            current += paragraph + "\n"
        else:
            sections.append(current.strip())
            current = paragraph + "\n"

    if current.strip():
        sections.append(current.strip())

    return sections

def remove_space_punctuation_isalnum(text):
    """Removes all non-alphanumeric characters (including spaces and punctuation) from a string."""
    cleaned_list = [char for char in text if char.isalnum()]
    return "".join(cleaned_list)

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

    text = clean_gutenberg_text(resp.text)
    sections = section_text(text)

    book = remove_space_punctuation_isalnum(title+authors)

    section_meta = [
        {"index": i + 1, 
            "starting_text":s[0:100],
            "file_present": os.path.exists(f"{os.path.join(app.root_path,'static', AUDIO_DIR)}/{book}_{i+1}.mp3"),
            "file_location": f"{AUDIO_DIR}/{book}_{i+1}.mp3"
            #"chars": len(s)
            }
        for i, s in enumerate(sections)
    ]

    return render_template(
        "sections.html",
        book_url=book_url,
        title=title,
        authors=authors,
        sections=section_meta
    )


@app.route("/generate", methods=['POST'])
def generate():
    book_url = request.form.get("book_url")
    title = request.form.get("title")
    authors = request.form.get("authors")
    section_num = int(request.form.get("section_num"))

    resp = requests.get(book_url)
    resp.raise_for_status()
    text = clean_gutenberg_text(resp.text)

    sections = section_text(text)

    if section_num < 1 or section_num > len(sections):
        return "Invalid section", 400

    book = remove_space_punctuation_isalnum(title+authors)
    #filename = f"static/{AUDIO_DIR}/{book}_{section_num}.mp3"
    filename = f"{os.path.join(app.root_path,'static', AUDIO_DIR)}/{book}_{section_num}.mp3"

    tts = gTTS(sections[section_num - 1], lang="en")
    tts.save(filename)

    # send_file may be an alternative setup? Not sure.
    #return send_file(
    #    filename,
    #    as_attachment=True,
    #    download_name=f"{book}_{section_num}.mp3"
    #)

    # file is already saved to static, so just need to reload page,
    # so that the file is available to play. :--)
    return redirect(url_for("show_book", book_url = book_url, title = title, authors = authors))

if __name__ == "__main__":
    static_dir = os.path.join(app.root_path, "static")
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)
    if not os.path.exists(os.path.join(static_dir, AUDIO_DIR)):
        os.makedirs(os.path.join(static_dir, AUDIO_DIR))
    app.run(debug=True)

