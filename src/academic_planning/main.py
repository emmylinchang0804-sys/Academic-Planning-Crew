from datetime import date

from .crew import AcademicPlanningCrew


def run(message):
    crew = AcademicPlanningCrew(today=date.today())
    return crew.plan_from_message(message)

