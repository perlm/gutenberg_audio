from flask import Flask, request, send_file, render_template
import requests
from gtts import gTTS
import os
import re

app = Flask(__name__)
AUDIO_DIR = "static/audio"
MAX_CHARS = 4000  # gTTS-safe section size

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
    return render_template("index.html")

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
    
    try:
        # Fetch book text
        resp = requests.get(book_url)
        resp.raise_for_status()

        text = clean_gutenberg_text(resp.text)
        sections = section_text(text)

        section_meta = [
            {"index": i + 1, 
                "starting_text":s[0:100]
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

    except Exception as e:
        return f"Error fetching: {e}"

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

    os.makedirs(AUDIO_DIR, exist_ok=True)

    # todo - include book id in file name? And then obviously hash in some way.
    book = remove_space_punctuation_isalnum(title+authors)
    filename = f"{AUDIO_DIR}/{book}_{section_num}.mp3"

    tts = gTTS(sections[section_num - 1], lang="en")
    tts.save(filename)

    return send_file(
        filename,
        as_attachment=True,
        download_name=f"section_{section_num}.mp3"
    )

if __name__ == "__main__":
    if not os.path.exists('static'):
        os.makedirs('static')
    app.run(debug=True)

