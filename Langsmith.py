# ============================================================
# Nümunə: İzləmənin aktiv olub-olmadığını yoxlamaq
# ============================================================

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# .env faylındakı açarları mühit dəyişəninə yükləyirik
load_dotenv()

# Əgər .env faylında yazmamısansa, əl ilə də təyin edə bilərsən
os.environ["LANGSMITH_TRACING"] = "true"
os.environ["LANGSMITH_ENDPOINT"] = "https://api.smith.langchain.com"
os.environ["LANGSMITH_PROJECT"] = "3nd_month_project"

# İzləmənin aktiv olub-olmadığını özümüz yoxlayaq
izleme_aktivdir = os.environ.get("LANGSMITH_TRACING") == "true"
print("İzləmə aktivdir?:", izleme_aktivdir)
print("Layihə adı:", os.environ.get("LANGSMITH_PROJECT"))

# Modeli yaradırıq
from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(model="claude-haiku-4-5-20251001")

# Sadə bir sorğu göndəririk - bu zəng AVTOMATİK olaraq LangSmith-ə yazılacaq
cavab = model.invoke("Salam! Sən kimsən, bir cümlə ilə təqdim et.")

print("\nModelin cavabı:", cavab.content)