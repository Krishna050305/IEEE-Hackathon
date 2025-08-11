from pymongo import MongoClient

uri = "mongodb+srv://apoorvmk457:apoorv.m.k@apoorv.bicllhf.mongodb.net/"

try:
    client = MongoClient(uri)
    db_list = client.list_database_names()
    print("✅ Connection successful!")
    print("Databases:", db_list)
except Exception as e:
    print("❌ Connection failed:", e)
