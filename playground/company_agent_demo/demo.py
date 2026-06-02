import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
import crewai.llms.cache as _cache

load_dotenv()

# cache_breakpoint is unsupported by Groq API — monkey-patch to no-op
_cache.mark_cache_breakpoint = lambda msg: msg

llm = LLM(model="groq/llama-3.3-70b-versatile")

# --- AGENTS ---

triage_agent = Agent(
    role="Customer Support Triage Specialist",
    goal="Categorize incoming customer complaints by urgency and type",
    backstory="Experienced support lead who quickly identifies the nature of complaints and prioritizes them accordingly",
    llm=llm,
    verbose=True
)

investigation_agent = Agent(
    role="Support Investigator",
    goal="Analyze the complaint in detail and identify the root cause and best resolution",
    backstory="Detail-oriented analyst who digs into customer issues and figures out exactly what went wrong and how to fix it",
    llm=llm,
    verbose=True
)

response_writer = Agent(
    role="Customer Response Writer",
    goal="Write a professional, empathetic email response to the customer",
    backstory="Senior customer success manager known for turning frustrated customers into loyal ones through clear, warm communication",
    llm=llm,
    verbose=True
)

# --- COMPLAINT ---

complaint = """
From: john.smith@example.com
Subject: Still haven't received my order - this is unacceptable

I placed order #48291 on November 3rd. It is now 3 weeks later and I have 
received nothing. No updates, no tracking info, no response to my two previous 
emails. I run a small business and ordered these supplies for a client project 
that has now been delayed because of this. I am extremely frustrated and want 
either my order delivered immediately or a full refund. If this isn't resolved 
today I will be disputing the charge with my bank.
"""

# --- TASKS ---

triage_task = Task(
    description=f"""
    Review this customer complaint and provide:
    1. Urgency level (Low / Medium / High / Critical)
    2. Complaint category (e.g. Shipping, Billing, Product, Support)
    3. Customer sentiment (Frustrated / Angry / Neutral etc.)
    4. A one-line summary of the issue

    Complaint:
    {complaint}
    """,
    expected_output="Urgency level, category, sentiment, and one-line summary",
    agent=triage_agent
)

investigation_task = Task(
    description="""
    Based on the triage summary, investigate the complaint thoroughly.
    Identify:
    1. What likely went wrong
    2. What the customer actually needs right now
    3. What resolution options are available (refund, reship, escalate, etc.)
    4. Your recommended resolution with reasoning
    """,
    expected_output="Root cause analysis and a clear recommended resolution",
    agent=investigation_agent,
    dependencies=[triage_task]
)

response_task = Task(
    description="""
    Using the investigation findings, write a professional and empathetic 
    email response to the customer. The email should:
    - Acknowledge the delay and apologize sincerely
    - Explain what happened briefly (without making excuses)
    - State clearly what action is being taken
    - Give a specific resolution timeline
    - End on a positive, reassuring note
    """,
    expected_output="A complete, ready-to-send customer email response",
    agent=response_writer,
    dependencies=[investigation_task]
)

# --- CREW ---

crew = Crew(
    agents=[triage_agent, investigation_agent, response_writer],
    tasks=[triage_task, investigation_task, response_task],
    verbose=True
)

print("\n" + "="*60)
print("RUNNING COMPANY AGENT DEMO — Customer Complaint Handler")
print("="*60 + "\n")

result = crew.kickoff()

print("\n" + "="*60)
print("FINAL OUTPUT — Draft Email Response")
print("="*60)
print(result)
