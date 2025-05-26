from selenium import webdriver

options = webdriver.ChromeOptions()
options.binary_location = "/usr/bin/chromium-browser"  # 强制指定 chromium 路径
driver = webdriver.Chrome(options=options)
driver.get("https://www.baidu.com")
input("Press Enter to quit...")
driver.quit()