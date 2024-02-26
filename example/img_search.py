from typing import Optional

from arclet.alconna import Alconna, Args, namespace


class Text:
    type = "text"
    text: str

    def __init__(self, t: str):
        self.text = t

    def __repr__(self):
        return self.text


class At:
    type = "At"
    target: int

    def __init__(self, t: int):
        self.target = t

    def __repr__(self):
        return f"At:{self.target}"

class Image:
    type = "image"
    src: str

    def __init__(self, url: str):
        self.src = url

    def __repr__(self):
        return f"Image:{self.src}"


with namespace("test") as np:
    np.to_text = lambda x: x.text if x.__class__ is Text else None
    alc = Alconna(
        "search",
        Args["img?", Image]
    )

@alc.bind()
def search(img: Optional[Image] = None):
    if not img:
        print("Please input your image")
    else:
        print(f"Searching {img.src} ...")

alc.parse([Text("search")])
alc.parse([Text("search"), Image("https://www.example.com/img")])
alc.parse([Text("search"), At(12345)])
