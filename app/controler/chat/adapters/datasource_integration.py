
from app.controler.chat.classes.project import Project


def generate_datasource_prompt(project: Project):
    project_datasources = project.datasources

    prompt = "Call this tool if you want to know more about the data sources available in this project.\n"
    prompt += "The data sources available are:\n"
    for datasource in project_datasources:
        prompt += "##" + datasource.description + "\n"

    return prompt
