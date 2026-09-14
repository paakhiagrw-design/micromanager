from app.agent import meeting_agent
from app.tools import tasks


sentence = "James will finish the database by Friday."

print("Meeting:")
print(sentence)

print("\nMicroManager processing...\n")

meeting_agent(sentence)

print("\nStored tasks:")
print(tasks)