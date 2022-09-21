import yaml
from datetime import datetime
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

root_url = "https://www.krisdika.go.th/web/guest/law?p_p_id=LawPortlet_INSTANCE_aAN7C2U5hENi&p_p_state=normal&p_p_mode=view&_LawPortlet_INSTANCE_aAN7C2U5hENi_javax.portlet.action=selectLawTypeMenu&_LawPortlet_INSTANCE_aAN7C2U5hENi_lawTypeId=4&p_auth=h8IfYmLl&p_p_lifecycle=0"

LAWS = [
  "ประมวลกฎหมายที่ดิน",
  "ประมวลกฎหมายแพ่งและพาณิชย์",
  "ประมวลกฎหมายวิธีพิจารณาความแพ่ง",
  "ประมวลกฎหมายวิธีพิจารณาความอาญา",
  "ประมวลกฎหมายอาญา",
  "ประมวลกฎหมายอาญาทหาร",
  "ประมวลรัษฎากร",
]

def async_find_element(driver, condition, timeout = 15):
  try:
    element = WebDriverWait(driver, timeout).until(
        EC.presence_of_element_located(condition)
    )
  except Exception:
    return None
  return element

def get_url(driver, law_title):
  element = async_find_element(driver, (By.XPATH, f"//span[contains(text(), '{law_title}')]"))
  if element is not None:
    element.click()
    a = async_find_element(driver, (By.XPATH, "//a[contains(text(), 'ล่าสุด')]"))
    
    url = a.get_attribute("href")
    name = a.text
    query_date = datetime.now()
    
    element.click()
    return {"url": url, "name": name, "query_date": query_date.strftime("%Y/%m/%d")}
  else:
    print(f"error: {law_title}")
    return "unknown"

def main():
  driver = webdriver.Chrome()
  driver.get(root_url)
  
  laws_url = {}
  for law_title in LAWS:
    laws_url[law_title] = get_url(driver, law_title)

  Path("./data").mkdir(parents=True, exist_ok=True)
  with open('data/urlmap.yaml', 'w') as f:
    yaml.dump(laws_url, f, default_flow_style=False, allow_unicode=True)
  input("\n\nPress enter to exit.")
  driver.quit()
  

if __name__=="__main__":
  main()