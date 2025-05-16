import os
import re
import json
from typing import List
import pandas as pd
from tqdm import tqdm
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from firecrawl import FirecrawlApp
from langchain_groq import ChatGroq
from langchain.schema import SystemMessage, HumanMessage
from langchain.output_parsers import PydanticOutputParser, OutputFixingParser

# Load environment variables
load_dotenv()

# ---------- Utilities ----------
def url_to_filename(url: str) -> str:
    return re.sub(r'[^a-zA-Z0-9]', '_', url).strip('_')

def ensure_output_dir(path='output'):
    os.makedirs(path, exist_ok=True)

# ---------- Pydantic Model ----------
class ProductItem(BaseModel):
    product_name: str = Field(description="Name of the product", default="n/a", alias="Product Description")
    product_link: str = Field(description="Link for the product detail", default="n/a", alias="Product Link")
    brand:str = Field(description="Brand of the product", default="n/a", alias="Brand")
    Flavors :List[str] = Field(description="List of flavors for the product", default=["n/a"], alias="Flavors")

class Listings(BaseModel):
    items: list[ProductItem]


# ---------- LLM Wrapper ----------
def extract_with_llm(data: str) -> dict:
    chat = ChatGroq(model_name="Qwen-Qwq-32b")
    parser = PydanticOutputParser(pydantic_object=Listings)
    fixing_parser = OutputFixingParser.from_llm(parser=parser, llm=chat)

    messages = [
        SystemMessage(content="You are a text extraction assistant. Extract structured data from messy real text for all the listed products and return only valid JSON."),
        HumanMessage(content=f"Extract the fields from the below given text.:\n\n{data}\n\nReturn JSON only, without extra information.:\n{parser.get_format_instructions()}")
    ]

    response = chat.invoke(messages)
    raw_output = response.content.strip()

    # Attempt to extract JSON content from the raw output
    try:
        json_str = re.search(r'\{.*\}', raw_output, re.DOTALL).group()
        parsed = parser.parse(json_str)
        return parsed.dict()
    except Exception as e:
        print(f"[Warning] Initial parse failed: {e}")
        print("[Info] Attempting to fix output with OutputFixingParser...")
        try:
            fixed = fixing_parser.parse(raw_output)
            return fixed.dict()
        except Exception as final_err:
            raise ValueError(f"Failed to extract ListingInfo. Final error: {final_err}\nRaw Output:\n{raw_output}")


# ---------- Scrape URL ----------
def scrape_markdown(url: str) -> str:
    app = FirecrawlApp()
    scraped_data = app.scrape_url(url, formats=['markdown'])
    if hasattr(scraped_data, "markdown"):
        return scraped_data.markdown
    elif isinstance(scraped_data, dict) and "markdown" in scraped_data:
        return scraped_data["markdown"]
    raise ValueError("No markdown found in scraped content.")

# ---------- Main Processing Logic ----------
def process_url(url: str, output_folder: str) -> list:
    filename_base = url_to_filename(url)
    raw_path = os.path.join(output_folder, f"{filename_base}.md")
    json_path = os.path.join(output_folder, f"{filename_base}.json")
    excel_path = os.path.join(output_folder, f"{filename_base}.xlsx")

    try:
        # Load or scrape raw markdowns
        if os.path.exists(raw_path):
            with open(raw_path, 'r', encoding='utf-8') as f:
                raw_data = f.read()
        else:
            raw_data = scrape_markdown(url)
            with open(raw_path, 'w', encoding='utf-8') as f:
                f.write(raw_data)

        # Load or extract structured data
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                structured_data = json.load(f)
        else:
            structured_data = extract_with_llm(raw_data)

            # Add home page URL to each item
            for item in structured_data["items"]:
                item["url"] = url

            # Save the enriched structured data to JSON
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(structured_data, f, indent=4)

            # Save to Excel
            pd.DataFrame(structured_data["items"]).to_excel(excel_path, index=False)

        # Build output with url, product_description, and product_link
        enriched_data = [
            {
                "url": item["url"],
                "product_description": item["product_description"],
                "product_link": item["product_link"]
            }
            for item in structured_data["items"]
        ]
        return enriched_data

    except Exception as e:
        # Return a placeholder row with the error
        return [{
            "url": url,
            "product_description": "ERROR",
            "product_link": str(e)
        }]

# ---------- Batch Runner ----------
def run_batch(url_list, output_folder="output", summary_path="output/summary.xlsx"):
    ensure_output_dir(output_folder)
    all_results = []

    print(f"Processing {len(url_list)} URLs...\n")
    for url in tqdm(url_list, desc="Processing URLs"):
        result = process_url(url, output_folder)
        all_results.extend(result) 

    df = pd.DataFrame(all_results)
    print(all_results)
    df.to_excel(summary_path, index=False)
    print(f"\nSummary saved to {summary_path}")


# ---------- Entry Point ----------
if __name__ == "__main__":
    urls = [
        "https://www.avtxwholesale.com/",
        "https://www.shopaairhus.com/",
        "https://mrawholesale.com/"
    ]

    run_batch(urls)
