from pathlib import Path

START = "<!-- CHOSEN_TODAY:START -->"
END = "<!-- CHOSEN_TODAY:END -->"

def update_readme(title, url, thumb):
    path = Path("README.md")
    text = path.read_text(encoding="utf-8")

    block = f"""
🎵 [**{title}**]({url})

<a href="{url}">
  <img src="{thumb}" width="320"/>
</a>
"""

    before = text.split(START)[0]
    after = text.split(END)[1]

    new_text = before + START + "\n" + block + "\n" + END + after
    path.write_text(new_text, encoding="utf-8")

