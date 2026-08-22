from flask import Flask, render_template

app = Flask(__name__)

SAMPLE_PDF_URL = (
    "https://img1.wsimg.com/blobby/go/3daad7b2-98c5-4dc1-b37a-5570afcba267/"
    "downloads/pipeline_isometric_drawing.pdf"
)


@app.route("/")
def index():
    return render_template("index.html", sample_pdf_url=SAMPLE_PDF_URL)


if __name__ == "__main__":
    app.run(debug=True)
