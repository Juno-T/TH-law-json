import os
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

from parser import LawParser

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
    # if law_title!="ประมวลกฎหมายวิธีพิจารณาความอาญา":
    #   continue
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
  parser.add_argument("--urlmap", type=str, default="./data/urlmap.yaml")
  parser.add_argument("--out", type=str, default="./data")
  args = parser.parse_args()
  path = Path(args.urlmap)
  assert path.is_file()
  Path(args.out).mkdir(parents=True, exist_ok=True)
  main(args)