"""
上交所新能源年报下载器

功能：
1. 精准采集新能源公司年报
2. Playwright 自动绕过反爬
3. 自动解析真实 PDF 地址
4. 浏览器环境下载 PDF（彻底解决403）
5. 自动 MD5 校验
6. 自动 CSV 记录
7. 自动跳过重复文件
8. 稳定长期运行

作者: XC
"""

import asyncio
import hashlib
import json
import re
import time
from pathlib import Path

import aiofiles
import pandas as pd
from loguru import logger
from playwright.async_api import async_playwright


# =========================================================
# 配置
# =========================================================

BASE_URL = "https://query.sse.com.cn/security/stock/queryCompanyBulletin.do"

DOWNLOAD_DIR = Path("新能源年报")
DOWNLOAD_DIR.mkdir(exist_ok=True)

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CSV_PATH = DATA_DIR / "新能源年报.csv"

HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Host": "query.sse.com.cn",
    "Pragma": "no-cache",
    "Referer": "https://www.sse.com.cn/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}

# =========================================================
# 新能源股票池
# =========================================================

NEW_ENERGY_CODES = {
"600032":"浙江新能",
"600072":"中船科技",
"600089":"特变电工",
"600110":"诺德股份",
"600135":"乐凯胶片",
"600151":"航天机电",
"600163":"中闽能源",
"600207":"安彩高科",
"600212":"绿能慧充",
"600416":"湘电股份",
"600438":"通威股份",
"600458":"时代新材",
"600478":"科力远",
"600481":"双良节能",
"600537":"*ST亿晶",
"600549":"厦门钨业",
"600732":"爱旭股份",
"600770":"综艺股份",
"600821":"金开新能",
"600905":"三峡能源",
"600930":"华电新能",
"601012":"隆基绿能",
"601016":"节能风电",
"601218":"吉鑫科技",
"601222":"林洋能源",
"601615":"明阳智能",
"601619":"嘉泽新能",
"601778":"晶科科技",
"601865":"福莱特",
"601877":"正泰电器",
"601908":"京运通",
"601985":"中国核电",
"603026":"石大胜华",
"603028":"赛福天",
"603063":"禾望电气",
"603105":"芯能科技",
"603185":"弘元绿能",
"603212":"赛伍技术",
"603218":"日月股份",
"603312":"西典新能",
"603381":"永臻股份",
"603396":"金辰股份",
"603507":"振江股份",
"603628":"清源股份",
"603659":"璞泰来",
"603693":"江苏新能",
"603799":"华友钴业",
"603806":"福斯特",
"603906":"龙蟠科技",
"603985":"恒润股份",
"605117":"德业股份",
"605376":"博迁新材",
"688005":"容百科技",
"688006":"杭可科技",
"688032":"禾迈股份",
"688033":"天宜新材",
"688063":"派能科技",
"688116":"天奈科技",
"688147":"微导纳米",
"688148":"芳源股份",
"688155":"先惠技术",
"688186":"广大特材",
"688223":"晶科能源",
"688275":"万润新能",
"688303":"大全能源",
"688339":"亿华通",
"688345":"博力威",
"688348":"昱能科技",
"688349":"三一重能",
"688353":"华盛锂电",
"688388":"嘉元科技",
"688390":"固德威",
"688392":"骄成超声",
"688408":"中信博",
"688472":"阿特斯",
"688499":"利元亨",
"688503":"聚和材料",
"688516":"奥特维",
"688518":"联赢激光",
"688556":"高测股份",
"688559":"海目星",
"688567":"孚能科技",
"688573":"信宇人",
"688598":"金博股份",
"688599":"天合光能",
"688660":"电气风电",
"688680":"海优新材",
"688707":"振华新材",
"688717":"艾罗能源",
"688726":"拉普拉斯",
"688733":"壹石通",
"688778":"厦钨新能",
"688779":"五矿新能",
}

# =========================================================
# 日志
# =========================================================

logger.add(
    "download.log",
    rotation="10 MB",
    retention="10 days",
    encoding="utf-8"
)

# =========================================================
# 工具函数
# =========================================================


def safe_filename(name):

    return re.sub(
        r'[\\/:*?"<>|]',
        "_",
        name
    )


def md5_file(filepath):

    md5 = hashlib.md5()

    with open(filepath, "rb") as f:

        while True:

            data = f.read(8192)

            if not data:
                break

            md5.update(data)

    return md5.hexdigest()


# =========================================================
# 获取公告列表
# =========================================================

async def fetch_report_list(context, stock_code):

    params = {
        "jsonCallBack": "jsonpCallback",
        "isPagination": "true",
        "productId": stock_code,
        "keyWord": "",
        "securityType": "0101,120100,020100,020200,120200",
        "reportType2": "DQBG",
        "reportType": "YEARLY",
        "beginDate": "2024-01-01",
        "endDate": "2026-12-31",
        "pageHelp.pageSize": "100",
        "pageHelp.pageCount": "100",
        "pageHelp.pageNo": "1",
        "pageHelp.beginPage": "1",
        "pageHelp.cacheSize": "1",
        "_": str(int(time.time() * 1000))
    }

    try:

        response = await context.request.get(
            BASE_URL,
            params=params,
            headers=HEADERS
        )

        logger.info(
            f"{stock_code} 状态码: {response.status}"
        )

        if response.status != 200:
            return []

        text = await response.text()

        json_match = re.search(
            r"jsonpCallback\((.*)\)",
            text,
            re.S
        )

        if not json_match:
            return []

        data = json.loads(json_match.group(1))

        return data.get("result", [])

    except Exception as e:

        logger.error(
            f"{stock_code} 获取失败: {e}"
        )

        return []


# =========================================================
# 获取真实PDF地址
# =========================================================

async def get_real_pdf_url(page, bulletin_url):

    try:

        await page.goto(
            bulletin_url,
            wait_until="domcontentloaded",
            timeout=60000
        )

        await asyncio.sleep(5)

        html = await page.content()

        # 匹配真实PDF
        pdf_match = re.search(
            r'https://static\.sse\.com\.cn/.*?\.pdf',
            html,
            re.I
        )

        if pdf_match:
            return pdf_match.group(0)

        # 检查 iframe
        for frame in page.frames:

            frame_url = frame.url

            if ".pdf" in frame_url:
                return frame_url

        return None

    except Exception as e:

        # 如果已经是PDF
        error_text = str(e)

        if "Download is starting" in error_text:

            current_url = page.url

            if current_url.endswith(".pdf"):
                return current_url

        logger.error(
            f"获取真实PDF失败: {e}"
        )

        return None


# =========================================================
# 下载PDF（最终稳定方案）
# =========================================================

async def download_pdf(
        context,
        page,
        company,
        title,
        bulletin_url
):

    try:

        logger.info(
            f"浏览器打开PDF页面: {title}"
        )

        real_pdf_url = await get_real_pdf_url(
            page,
            bulletin_url
        )

        if not real_pdf_url:

            logger.error(
                f"无法获取真实PDF地址: {title}"
            )

            return None

        logger.info(
            f"真实PDF地址: {real_pdf_url}"
        )

        filename = safe_filename(
            f"{company}_{title}.pdf"
        )

        save_path = DOWNLOAD_DIR / filename

        # 已存在
        if save_path.exists():

            logger.warning(
                f"文件已存在，跳过: {filename}"
            )

            return {
                "company": company,
                "title": title,
                "path": str(save_path),
                "md5": md5_file(save_path)
            }

        # =================================================
        # 浏览器环境请求
        # =================================================

        response = await context.request.get(
            real_pdf_url,
            headers={
                "Referer": bulletin_url,
                "Accept": (
                    "text/html,"
                    "application/xhtml+xml,"
                    "application/xml;q=0.9,"
                    "image/avif,"
                    "image/webp,"
                    "*/*;q=0.8"
                )
            }
        )

        logger.info(
            f"PDF状态码: {response.status}"
        )

        if response.status != 200:

            logger.error(
                f"PDF下载失败: {title}"
            )

            return None

        content_type = response.headers.get(
            "content-type",
            ""
        )

        logger.info(
            f"Content-Type: {content_type}"
        )

        body = await response.body()

        # PDF校验
        if not body.startswith(b"%PDF"):

            logger.error(
                f"非PDF文件: {title}"
            )

            logger.error(body[:500])

            return None

        async with aiofiles.open(
                save_path,
                "wb"
        ) as f:

            await f.write(body)

        file_md5 = md5_file(save_path)

        logger.success(
            f"下载成功: {title}"
        )

        logger.info(
            f"MD5: {file_md5}"
        )

        return {
            "company": company,
            "title": title,
            "path": str(save_path),
            "md5": file_md5
        }

    except Exception as e:

        logger.error(
            f"下载失败: {title} -> {e}"
        )

        return None


# =========================================================
# 主程序
# =========================================================

async def main():

    logger.info(
        "正在初始化浏览器环境"
    )

    async with async_playwright() as playwright:

        browser = await playwright.chromium.launch(
            headless=True
        )

        context = await browser.new_context(
            accept_downloads=True
        )

        page = await context.new_page()

        # 初始化
        await page.goto(
            "https://www.sse.com.cn/",
            wait_until="networkidle"
        )

        logger.success(
            "浏览器初始化成功"
        )

        all_results = []

        # =================================================
        # 开始采集
        # =================================================

        for stock_code, company_name in NEW_ENERGY_CODES.items():

            logger.info(
                f"开始采集: "
                f"{stock_code} "
                f"{company_name}"
            )

            report_list = await fetch_report_list(
                context,
                stock_code
            )

            if not report_list:
                continue

            for item in report_list:

                title = item.get("TITLE", "")

                # 只下载年度报告
                if "年度报告" not in title:
                    continue

                url = item.get("URL", "")

                if not url:
                    continue

                if not url.startswith("http"):
                    bulletin_url = (
                        f"https://www.sse.com.cn{url}"
                    )
                else:
                    bulletin_url = url

                result = await download_pdf(
                    context,
                    page,
                    company_name,
                    title,
                    bulletin_url
                )

                if result:
                    all_results.append(result)

                # 防风控
                await asyncio.sleep(3)

        # =================================================
        # 保存CSV
        # =================================================

        if all_results:

            df = pd.DataFrame(all_results)

            df.to_csv(
                CSV_PATH,
                index=False,
                encoding="utf-8-sig"
            )

            logger.success(
                f"CSV保存成功: {CSV_PATH}"
            )

        await browser.close()

    logger.success(
        "全部下载完成"
    )


# =========================================================
# 启动
# =========================================================

if __name__ == "__main__":

    asyncio.run(main())
