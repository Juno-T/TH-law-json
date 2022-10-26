from typing import Any
import yaml

import pandas as pd
import pythainlp as ptn

# TODO: add meta (scrape date)

# make sure that these tokens match the keywords.yaml
__law_title__ = "law_title"
__law_footer__ = "law_footer"
__law_body__ = "body"
__provision__ = "provision"
__provision_footer__ = "provision_footer"
__index__ = "index"
__body_header__ = "body_header"
__division__ = "division"
__subdivision__ = "subdivision"
__chapter__ = "chapter"
__section__ = "section"
__article__ = "article"
__extra__ = "extra"

__titled_tokens__ = [
  __index__,
  __division__,
  __subdivision__,
  __chapter__,
  __section__
]

__law_body_tokens__ = [
  __division__,
  __subdivision__,
  __chapter__,
  __section__,
  __article__,
  __extra__
]

__text_tokens__ = [
  __article__,
  __law_footer__,
  __provision_footer__,
]

def get_prefix_digits(s: str):
  for i, c in enumerate(s):
    if not c.isdigit():
      return s[:i]
  return s

def parse_key(idx_str: str):
  """
  premise:
    1. contains atleast two parts, sep by ' '.
    2. the number is in the second part. Its suffix starts with symbol.
  """
  try:
    num_part = idx_str.split(' ')[1]
    num_part = ptn.util.thai_digit_to_arabic_digit(num_part)
    index = get_prefix_digits(num_part)
  except:
    return idx_str
  if len(index)==0:
    return idx_str
  return index

class Stack:
  def __init__(self):
    self.stack = []
  
  def push(self, token: str, level: int, data: Any):
    self.stack.append({"token": token, "level": level, "data": data})

  def pop(self):
    return self.stack.pop()

  def top(self):
    return self.stack[-1]
  
  def update_top(self, token: str, level: int, data: Any):
    self.stack[-1]={"token": token, "level": level, "data": data}
  
  def to_dict(self):
    i=0
    while(i < len(self.stack) and self.stack[i]["token"] != __law_title__):
      i+=1
    if i == len(self.stack):
      return None
    i+=1
    row = {}
    while(i < len(self.stack)):
      token = self.stack[i]["token"]
      data = self.stack[i]["data"]
      key = parse_key(data["key"])
      row[token]=key
      if "title" in data["content"]:
        row[token+"_name"] = data["content"]["title"]
      i+=1
    return row

  def __len__(self):
    return len(self.stack)

class LawParser:
  """
    Premise:
      1. Keywords are according to keywords.yaml
      2. Keywords with title (__titled_tokens__) have their title centered in the next paragraph.
      3. Law body starts with non-titled, centered __law_title__.
      4. __text_tokens__ don't have title or children.
      5. Centered paragraph inside __law_body_tokens__ will be classified as non-titled extra token.
      6. Ignore remarks (law editting remarks etc.)
  """
  def __init__(self, title: str):
    self.title = title
    self._stack = Stack()
    self._stack.push("top level", -1, {})
    self.df_rows = []

    with open("keywords.yaml", 'r') as f:
      self._keywords = yaml.safe_load(f)
      assert(len(self._keywords.items())>0)
    self._keywords[self.title]=self._keywords[__law_title__]
  
  def parse_paragraph(self, text: str, alignment: str=""):
    text = text.strip(' \t\n\r')
    if len(text)==0:
      return
    if alignment == "center" or text==self.title:
      # ประมวลกฎหมายอาญา's title alignment != center
      # check if parent needs title, if so, add title and return
      # else, check keyword. If not a keyword, add text to parent.
      # else, pop lower level node until a parent is found, push to stack.
      top = self._stack.top()
      if not "content" in top["data"]:
        top["data"]["content"]={}
      if not "title" in top["data"]["content"] and top["token"] in __titled_tokens__:
        top["data"]["content"]["title"] = text
        self._stack.update_top(**top)
        return
      
      kw = self._keywords.get(text.split(" ")[0], None)
      if kw is None and top["token"] in __law_body_tokens__:
          kw = self._keywords[__extra__]

      if kw is None:
        self.add_text_to_parent(text)
      else:
        while len(self._stack)>0:
          top = self._stack.top()
          if top["level"]<kw["level"]:
            break
          self.fold()

        # Push to stack. The content depends if the token is leaf.
        key = " ".join(text.split(" ")[:2])
        if kw["token"] in __text_tokens__:
          data={"content": {"text": text+"\n"}}
        else:
          data={"key": key, "content": {}}
        self._stack.push(
          kw["token"], 
          kw["level"], 
          data
        )

    elif alignment == "right":
      # For law footer
      # pop stack till root and push footer
      top = self._stack.top()
      if top["token"]!=__law_footer__:
        while len(self._stack)>0:
          top = self._stack.top()
          if top["level"]<0:
            break
          self.fold()
        self._stack.push(
          __law_footer__, 
          self._keywords[__law_footer__]["level"], 
          {"content": {"text": text+"\n"} }
        )
      else:
        self.add_text_to_parent(text)

    else:
      # No alignment paragraph
      # Check if it's an article, if so, pop same level and push to stack
      # else, add text to parent
      res = self.parse_article(text)
      if res is not None:
        # if it is a new article
        while len(self._stack)>0:
          top = self._stack.top()
          if top["level"]<res["level"]:
            break
          self.fold()
        self._stack.push(**res)
      else:
        self.add_text_to_parent(text)
  
  def fold(self):
    top = self._stack.pop()
    parent = self._stack.top()
    if not "content" in parent["data"]:
      parent["data"]["content"]={}

    if not "key" in top["data"]:
      # unique token
      parent["data"]["content"][top["token"]]=top["data"]["content"]
    elif top["token"]==__law_title__:
      # top level
      parent["data"]["content"][__law_body__] = top["data"]["content"]
    else:
      # sequential token
      if not top["token"] in parent["data"]["content"]:
        parent["data"]["content"][top["token"]]={}
      key = parse_key(top["data"]["key"])
      if not key in parent["data"]["content"][top["token"]]:
        # ignore remarks.
        parent["data"]["content"][top["token"]][key]=top["data"]["content"]
        if top["token"]==__article__:
          self.add_article_to_table(top, key)
    self._stack.update_top(**parent)

  def add_text_to_parent(self, text):
    # add to existing parent
    # directly to content if it's __text_tokens__, else to "text"
    top = self._stack.top()
    if not "content" in top["data"]:
      top["data"]["content"]={}
    if not "text" in top["data"]["content"]:
      top["data"]["content"]["text"]=""
    top["data"]["content"]["text"]+=text+"\n"
    self._stack.update_top(**top)


  def parse_article(self, text):
    splitted_text = text.split(" ")
    if len(splitted_text)>=2:
      kw = splitted_text[0]
      key = " ".join(splitted_text[:2])
      kw = self._keywords.get(kw, None)
      if kw is None:
        return None
      if kw["token"]==__article__:
        article = {
          "token": __article__,
          "level": kw["level"],
          "data":{
            "key": key,
            "content": {"text": text},
          }
        }
        return article
    return None
  
  def add_article_to_table(self, article, key):
    assert article["token"]==__article__
    # construct row
    row = self._stack.to_dict()
    if row is None:
      return
    row["text"]=article["data"]["content"]["text"].replace("\n", "__newline__")
    row[__article__] = key
    # ignore remarks
    if len(self.df_rows)>0:
      prev_row = self.df_rows[-1]
      if int(row[__article__])<int(prev_row[__article__]):
        return
    self.df_rows.append(row)

  def get_df_column_order(self, original_column):
    ordered_kw = list(self._keywords.keys())
    # sort col by level
    ordered_kw.sort(key=lambda x: self._keywords[x]["level"])
    ordered_column=[]
    for kw in ordered_kw:
      c = self._keywords[kw]["token"]
      if c in original_column and c not in ordered_column:
        ordered_column.append(c)
      if c+"_name" in original_column and c+"_name" not in ordered_column:
        ordered_column.append(c+"_name")
    if "text" in original_column:
      ordered_column.append("text")
    return ordered_column

  def conclude(self):
    while len(self._stack)>1:
      top = self._stack.top()
      if top["level"]==-1:
        break
      self.fold()
    top = self._stack.pop()
    law_dict = {
      "title": self.title,
      **top["data"]["content"]
    }

    law_df = pd.DataFrame(self.df_rows)
    ordered_column = self.get_df_column_order(law_df.columns)
    return law_dict, law_df[ordered_column]