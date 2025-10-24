# athlete-data-platform
Data platform with ADF + Databricks + Strava integration

🏃‍♂️ Project Atlhete! — Personal Performance Platform with Strava Data
## 📊 Architecture Diagram
You can explore the interactive architecture of the project in the link below:

👉 [Open Architecture Diagram (HTML)](https://luisgustavocorrea.github.io/Architecture-Design/)]

Example of PDF report cover generated with Strava data.

📌 Overview
This is a personal fitness analytics platform designed to integrate Strava data with a modern cloud data architecture. The goal is to track workouts, extract meaningful performance metrics, and generate personalized reports for each authenticated athlete.

🔐 Authentication
Users authenticate via OAuth using Strava’s official API. Only the athlete’s own data is accessed, in full compliance with Strava’s API Terms and privacy guidelines.

⚙️ Technical Architecture
Raw Layer: Stores original JSON files from Strava in Azure Data Lake (e.g., raw/strava/activities/date=YYYY-MM-DD/activity_12:32:10_GUID.json)

Bronze/Silver/Gold Layers: Incremental processing using Delta Lake on Databricks.

Pipelines: Automated with Azure Data Factory.

Visualization: Currently via PDF reports automatically generated and delivered to the athlete.

Security: Tokens secured via Azure Key Vault and access managed with Azure Entra ID.

📊 Metrics Extracted
Distance (km)

Average pace (min/km)

Elevation gain per km

Workout duration

Weekly and monthly activity distribution

Period-over-period performance comparison

📄 Reports

Summary section of a personalized PDF report.

Currently, the platform generates dynamic PDF reports for each athlete based on their Strava data. These reports include personalized charts, metrics, and written insights in a storytelling format.

In the future, we plan to evolve this reporting into interactive dashboards using tools like Power BI.

🔒 Compliance
✔️ Follows Strava API Terms
✔️ Complies with Strava Brand Guidelines
✔️ Tokens encrypted and stored securely
✔️ Data used exclusively by authenticated users for their own insights

🧠 Next Steps
Support for multiple authenticated users

Token management with Azure Key Vault and control tables

CI/CD implementation for pipeline deployments

Interactive dashboards based on the current PDF storytelling reports

🙋‍♂️ Developed by
Luis Corrêa
LinkedIn:
https://www.linkedin.com/in/luis-gustavo-284809113?utm_source=share&utm_campaign=share_via&utm_content=profile&utm_medium=ios_app
