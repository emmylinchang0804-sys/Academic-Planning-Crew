from .workflows.planning_flow import plan_activity


class AcademicPlanningCrew:
    def __init__(self, today=None):
        self.today = today

    def plan_from_message(self, message, context=None):
        return plan_activity(message, context or {}, today=self.today)

