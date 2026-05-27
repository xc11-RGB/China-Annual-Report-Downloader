"""
北交所新能源年报下载系统（最终完整版）

功能：
1. 自动打开北交所公告页面
2. 搜索新能源公司名称
3. 自动筛选“年度报告”
4. 自动过滤摘要/临时公告
5. 自动翻页
6. 自动下载真实PDF
7. PDF可正常打开

安装：
pip install playwright requests loguru

初始化：
playwright install
"""

import os
import re
import time
import requests

from urllib.parse import urljoin
from playwright.sync_api import sync_playwright
from loguru import logger


# =========================================================
# 配置
# =========================================================

BASE_URL = "https://www.bse.cn/disclosure/announcement.html"

DOWNLOAD_DIR = "北交所新能源年报"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0 Safari/537.36"
    )
}

# 新能源公司
NEW_ENERGY_COMPANIES = [
    "中航泰达",
    "丰光精密",
    "惠丰钻石",
    "力佳科技",
    "凯德石英",
    "禾昌聚合",
    "贝特瑞"


]

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# =========================================================
# 工具函数
# =========================================================

def safe_filename(name):
    """
    清理非法字符
    """
    return re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", name)


def is_real_annual_report(title):
    """
    判断是否是真正年报
    """

    if "年度报告" not in title:
        return False

    exclude_keywords = [
        "摘要",
        "英文",
        "取消",
        "说明会",
        "独立董事",
        "监事",
        "审计",
        "公告",
        "更正",
    ]

    for word in exclude_keywords:
        if word in title:
            return False

    return True


def download_pdf(url, filename):
    """
    下载PDF
    """

    try:

        logger.info(f"开始下载: {filename}")

        response = requests.get(
            url,
            headers=HEADERS,
            stream=True,
            timeout=60
        )

        logger.info(f"PDF状态码: {response.status_code}")

        if response.status_code != 200:
            logger.error("下载失败")
            return False

        content_type = response.headers.get("Content-Type", "")

        if "pdf" not in content_type.lower():
            logger.error(f"不是PDF文件: {content_type}")
            return False

        filepath = os.path.join(
            DOWNLOAD_DIR,
            safe_filename(filename) + ".pdf"
        )

        with open(filepath, "wb") as f:

            for chunk in response.iter_content(chunk_size=10240):

                if chunk:
                    f.write(chunk)

        logger.success(f"下载成功: {filepath}")

        return True

    except Exception as e:

        logger.error(f"下载失败: {e}")

        return False


# =========================================================
# 搜索公司
# =========================================================

def search_company(page, company_name):
    """
    搜索公司名称
    """

    logger.info(f"开始搜索: {company_name}")

    search_selectors = [
        'input[placeholder*="关键字"]',
        'input[placeholder*="请输入"]',
        'input'
    ]

    search_input = None

    for selector in search_selectors:

        try:

            page.wait_for_selector(selector, timeout=5000)

            search_input = page.locator(selector).first

            logger.success(f"找到搜索框: {selector}")

            break

        except:
            pass

    if not search_input:
        logger.error("未找到搜索框")
        return False

    try:

        # 清空
        search_input.click()

        page.keyboard.press("Control+A")

        page.keyboard.press("Backspace")

        time.sleep(1)

        # 输入公司名称
        search_input.fill(company_name)

        logger.success(f"已输入公司名称: {company_name}")

        time.sleep(1)

        # 回车搜索
        page.keyboard.press("Enter")

        logger.success("已执行搜索")

        time.sleep(8)

        return True

    except Exception as e:

        logger.error(f"搜索失败: {e}")

        return False


# =========================================================
# 解析页面
# =========================================================

def parse_current_page(page, company_name):
    """
    解析当前页
    """

    reports = []

    rows = page.locator("tbody tr")

    count = rows.count()

    logger.info(f"发现公告行数量: {count}")

    for i in range(count):

        try:

            row = rows.nth(i)

            text = row.inner_text().strip()

            logger.info(f"公告内容: {text}")

            if company_name not in text:
                continue

            if not is_real_annual_report(text):
                continue

            cols = text.split("\t")

            if len(cols) < 4:
                continue

            code = cols[0]

            title = cols[2]

            date = cols[-1]

            # 获取真实PDF链接
            links = row.locator("a")

            pdf_url = None

            for j in range(links.count()):

                href = links.nth(j).get_attribute("href")

                if not href:
                    continue

                if ".pdf" in href.lower():

                    pdf_url = urljoin(
                        "https://www.bse.cn",
                        href
                    )

                    break

            if not pdf_url:
                logger.warning("未找到PDF")
                continue

            logger.success(f"发现年报: {company_name}")

            logger.info(f"真实PDF: {pdf_url}")

            reports.append({
                "company": company_name,
                "code": code,
                "title": title,
                "date": date,
                "pdf_url": pdf_url
            })

        except Exception as e:

            logger.error(f"解析失败: {e}")

    return reports


# =========================================================
# 翻页
# =========================================================

def goto_next_page(page):
    """
    下一页
    """

    selectors = [
        'button:has-text("下一页")',
        'a:has-text("下一页")',
        '.next',
        '.pagination-next',
    ]

    for selector in selectors:

        try:

            btn = page.locator(selector)

            if btn.count() > 0:

                button = btn.first

                if button.is_enabled():

                    logger.info("正在翻页...")

                    button.click()

                    time.sleep(5)

                    return True

        except:
            pass

    return False


# =========================================================
# 主程序
# =========================================================

def main():

    logger.info("北交所新能源年报系统启动")

    all_reports = []

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=False
        )

        page = browser.new_page()

        page.goto(BASE_URL)

        logger.success("公告页面打开成功")

        time.sleep(5)

        # =================================================
        # 遍历公司
        # =================================================

        for company in NEW_ENERGY_COMPANIES:

            logger.info("=" * 60)

            logger.info(f"开始处理: {company}")

            success = search_company(page, company)

            if not success:
                continue

            current_page = 1

            while True:

                logger.info(f"开始采集第 {current_page} 页")

                reports = parse_current_page(page, company)

                if reports:

                    all_reports.extend(reports)

                    logger.success(
                        f"{company} 找到年报数量: {len(reports)}"
                    )

                    # 找到即停止翻页
                    break

                logger.info("当前页未找到年报，继续翻页")

                has_next = goto_next_page(page)

                if not has_next:

                    logger.warning("无法继续翻页")

                    break

                current_page += 1

            time.sleep(2)

        # =================================================
        # 去重
        # =================================================

        unique_reports = []

        seen = set()

        for r in all_reports:

            key = r["pdf_url"]

            if key not in seen:

                seen.add(key)

                unique_reports.append(r)

        logger.success(f"最终年报数量: {len(unique_reports)}")

        # =================================================
        # 下载PDF
        # =================================================

        success_count = 0

        for report in unique_reports:

            filename = (
                f"{report['company']}_"
                f"{report['title']}_"
                f"{report['date']}"
            )

            ok = download_pdf(
                report["pdf_url"],
                filename
            )

            if ok:
                success_count += 1

            time.sleep(1)

        logger.success(f"成功下载数量: {success_count}")

        browser.close()

    logger.success("全部下载完成")


# =========================================================
# 启动
# =========================================================

if __name__ == "__main__":
    main()
