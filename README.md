## Web Scraping and Feature/Attribute Extraction

The process begins with the use of FireCrawlApp to load the content of one or multiple websites concurrently, excluding HTML tags. This results in semi-structured data, which is then passed to a Large Language Model (LLM) for further processing.

The LLM utilizes a Pydantic BaseModel along with an output fixing parser to extract structured (json ,excel) data containing various attributes of interest.

## Workflow 

![Image](https://github.com/user-attachments/assets/398e16cf-8192-437e-b8e3-dcf70fa1bdb1)
