import re
import requests
from datetime import datetime
from PIL import Image
from io import BytesIO
import openai
import os
import csv
from collections import Counter
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize

nltk.download('punkt')
nltk.download('stopwords')

# Directory for saving images
image_dir = 'images'
os.makedirs(image_dir, exist_ok=True)

# Ensure that the environment variable OPENAI_API_KEY is set in your environment before running this script.
openai.api_key = "sk-XXXXX"

# Corrected the regular expression for safe filenames
SAFE_FILENAME_PATTERN = re.compile(r'[^\w\-_]')

def safe_filename(filename):
    return SAFE_FILENAME_PATTERN.sub('', filename)

def generate_article(topic):
    print(f"Generating article on the topic: {topic}")
    try:
        instruction = ("Write a detailed article about {}. Output should be HTML. "
                       "Do not end headings with 'in the Australian context', "
                       "avoid concluding the article with the word 'Conclusion', "
                       "avoid including 'Australia' in the heading, and "
                       "avoid including 'Australian' in the heading. "
                       "Include references to Australian legislation, best practices, and "
                       "any other relevant local context.")
        response = openai.ChatCompletion.create(
            model="gpt-4-1106-preview",
            messages=[
                {"role": "system", "content": "You are an expert writer. Use an informative voice writing style. Only output HTML. NEVER add any text before or after the article."},
                {"role": "user", "content": instruction.format(topic)}
            ],
            temperature=0.5
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        return str(e)

def summarize_article(article):
    print("Summarizing article in three words.")
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-1106",
            messages=[
                {
                    "role": "user",
                    "content": f"Provide a maximum three-word summary of this article, focusing on the main technical topic or theme. \n\n'''{article}'''"
                }
            ],
            temperature=0.7,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        return response.choices[0].message['content'].strip()
    except Exception as e:
        return str(e)

def generate_excerpt(article, max_length=300):
    """ Generate an excerpt by taking the first max_length characters from the article. """
    return article[:max_length]

def generate_dalle3_image(summary, url_safe_article_title):
    print(f"Generating image for {url_safe_article_title}.")
    try:
        response = openai.Image.create(
            model="dall-e-3",
            prompt=f"Create a technical illustration of a '{summary}'. The drawing should use multiple lines to depict the detailed structure and components commonly found in '{summary}'. The focus should be on accuracy and clarity, providing a precise and informative view of the '{summary}'. The style should resemble a schematic or blueprint, commonly used in engineering and technical documentation, with clear lines set against a solid block color background of hex #2c4a20. Do not include words. Do not include numbers.",
            size="1792x1024",
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url
        image_response = requests.get(image_url)

        if image_response.status_code == 200:
            image = Image.open(BytesIO(image_response.content))
            image_filename = os.path.join(image_dir, f'{url_safe_article_title}.png')
            image.save(image_filename)
            print(f"Image saved as '{image_filename}'")
            return image_filename
        else:
            raise Exception("Failed to download the generated image")
    except Exception as e:
        print(str(e))
        return None

def format_html(article, article_title, url_safe_article_title, summary):
    title = article_title  # Use the original article title for the title

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{title}</title>
    <meta name="publishedAt" content="{datetime.now().strftime('%Y-%m-%d')}">
</head>
<body>
    {article}
</body>
</html>
"""
    return html_content

def save_to_html_file(content, filename):
    html_path = f"./{filename}.html"
    print(f"Saving article to {html_path}")
    try:
        with open(html_path, "w") as file:
            file.write(content)
        print(f"Article successfully saved as {filename}.html")
    except Exception as e:
        print(f"Failed to save article {filename}.html: {e}")

def save_to_csv(file_path, data, categories, tags, image_filename, excerpt):
    with open(file_path, 'a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(data + [', '.join(categories), ', '.join(tags), image_filename, image_filename, excerpt])

if __name__ == "__main__":
    output_csv = 'articles_summary.csv'
    with open(output_csv, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['Article Title', 'Content (HTML)', 'Categories', 'Tags', 'Image', 'Featured Image', 'Excerpt'])

    with open('topics.csv', newline='') as csvfile:
        topics_reader = csv.reader(csvfile)
        for row in topics_reader:
            article_title = row[0]
            url_safe_article_title = safe_filename(article_title.replace(" ", "-"))

            article = generate_article(article_title)
            if article:
                summary = summarize_article(article)
                html_content = format_html(article, article_title, url_safe_article_title, summary)
                html_filename = f"{url_safe_article_title}.html"
                save_to_html_file(html_content, url_safe_article_title)

                excerpt = generate_excerpt(article)

                words = word_tokenize(summary.lower())
                words = [word for word in words if word.isalpha()]
                words = [word for word in words if word not in stopwords.words('english')]
                most_common_words = [word for word, word_count in Counter(words).most_common(6)]
                categories = most_common_words[:6]
                tags = most_common_words[-2:]

                try:
                    image_filename = generate_dalle3_image(summary, url_safe_article_title)
                    image_path = os.path.join(image_dir, image_filename)
                    save_to_csv(output_csv, [article_title, html_content], categories, tags, image_path, excerpt)
                except Exception as e:
                    print(str(e))
            else:
                print(f"Failed to generate the article for topic: {article_title}")
