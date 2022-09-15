import os
from typing import Any
import yaml
import json
import time
import argparse
from pathlib import Path
from tqdm import tqdm

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# TODO: exclude footers (แก้ไขเพิ่มเติมประมวลกฎหมาย, มาตรา, หมายเหตุ)
# TODO: add meta (scrape date)

__law_title__ = "law_title"
__law_footer__ = "law_footer"
__law_body__ = "body"
__provision__ = "provision"
__provision_footer__ = "provision_footer"
__body_header__ = "body_header"
__division__ = "division"
__subdivision__ = "subdivision"
__chapter__ = "chapter"
__section__ = "section"
__article__ = "article"
__extra__ = "extra"

__titled_tokens__ = [
  __division__,
  __subdivision__,
  __chapter__,
  __section__
]

__law_body_tokens__ = __titled_tokens__+[__article__,__extra__]

__footer_tokens__ = [
  __law_footer__,
  __provision_footer__,
]

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

  def __len__(self):
    return len(self.stack)

class LawParser:
  def __init__(self, title: str):
    self.title = title
    self._stack = Stack()
    self._stack.push("top level", -1, {})

    with open("keywords.yaml", 'r') as f:
      self._keywords = yaml.safe_load(f)
      assert(len(self._keywords.items())>0)
    self._keywords[self.title]=self._keywords[__law_title__]
  
  def parse_paragraph(self, text: str, alignment: str=""):
    text = text.strip()
    if len(text)==0:
      return
    if alignment == "center":
      # check if parent needs title
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
        # add to existing parent
        # to title if not yet exist
        # to content if it's string, else to header
        if not "content" in top["data"]:
          top["data"]["content"]={}
        if top["token"] in __footer_tokens__:
          top["data"]["content"]+=text+"\n"
        else:
          if not "header" in top["data"]["content"]:
            try:
              top["data"]["content"]["header"]=""
            except:
              print(text)
          top["data"]["content"]["header"]+=text+"\n"
        self._stack.update_top(**top)
      else:
        while len(self._stack)>0:
          top = self._stack.top()
          if top["level"]<kw["level"]:
            break
          self.fold()

        key = " ".join(text.split(" ")[:2])
        if kw["token"] in __footer_tokens__:
          data={"content": text+"\n"}
        else:
          data={"key": key, "content": {}}

        self._stack.push(kw["token"], kw["level"], data)

    elif alignment == "right":
      # For law footer
      top = self._stack.top()
      if top["token"]!=__law_footer__:
        while len(self._stack)>0:
          top = self._stack.top()
          if top["level"]<0:
            break
          self.fold()
        self._stack.push(__law_footer__, self._keywords[__law_footer__]["level"], {"content": text+"\n"} )
      else:
        top["data"]["content"]+=text+"\n"
        self._stack.update_top(**top)

    else:
      # No alignment paragraph -> ignore higher level token
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
        top = self._stack.top()
        if top["token"]==__article__:
          top["data"]["content"]+=text
        else:
          if not "content" in top["data"]:
            top["data"]["content"]={}
          if not "header" in top["data"]["content"]:
            top["data"]["content"]["header"]=""

          top["data"]["content"]["header"]+=text+"\n"
        self._stack.update_top(**top)
  
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
      parent["data"]["content"][top["token"]][top["data"]["key"]]=top["data"]["content"]
    self._stack.update_top(**parent)

  def parse_article(self, text):
    splitted_text = text.split(" ")
    if len(splitted_text)>=2:
      kw, num = splitted_text[0], splitted_text[1]
      kw = self._keywords.get(kw, None)
      if kw is None:
        return None
      if kw["token"]==__article__:
        return {
          "token": __article__,
          "level": kw["level"],
          "data":{
            "key": num,
            "content": text,
          }
        }
      else:
        print(f"Not expecting token \"{kw['token']}\" of text \"{text}\" here")
        return None
    else:
      return None
      
  def conclude(self):
    while len(self._stack)>1:
      top = self._stack.top()
      if top["level"]==-1:
        break
      self.fold()
    top = self._stack.pop()
    return {
      "title": self.title,
      **top["data"]["content"]
    }



def async_find_element(driver, condition, timeout = 15):
  try:
    element = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located(condition)
    )
  except Exception:
    return None
  return element

def parse_law_body(law_title, law_body):
  parser = LawParser(law_title)
  paragraphs = law_body.find_elements(By.XPATH, "./p")
  print("#paragraphs:",len(paragraphs))
  for p in tqdm(paragraphs):
    alignment = p.get_attribute("align")
    text = p.text.strip()
    parser.parse_paragraph(text, alignment)
  return parser.conclude()


def scrape_body_html(driver, url):
  driver.get(url)
  driver.switch_to.frame(async_find_element(driver, (By.XPATH, "//frame[@name='top']")))
  body = async_find_element(driver, (By.TAG_NAME, "body"))
  law_body, law_footnote = body.find_elements(By.XPATH, "./div") # premise: 2 div in the body
  return law_body

def main(args):
  driver = webdriver.Chrome()
  
  with open(args.urlmap, 'r') as f:
    laws_url = yaml.safe_load(f)
    assert(len(laws_url.items())>0)
    
  for law_title in laws_url:
    if law_title!="ประมวลกฎหมายวิธีพิจารณาความอาญา":
      continue
    print(law_title)
    url = laws_url[law_title]["url"]
    law_body = scrape_body_html(driver, url)
    res = parse_law_body(law_title, law_body)
    with open(os.path.join(args.out,f'{law_title}.json'), 'w', encoding='utf8') as f:
      json.dump(res, f, indent=1, ensure_ascii=False)
  input("\n\nPress enter to exit.")
  driver.quit()
  

if __name__=="__main__":
  parser = argparse.ArgumentParser()
  parser.add_argument("--urlmap", type=str, default="./urlmap.yaml")
  parser.add_argument("--out", type=str, default="./data")
  args = parser.parse_args()
  path = Path(args.urlmap)
  assert path.is_file()
  Path(args.out).mkdir(parents=True, exist_ok=True)
  main(args)