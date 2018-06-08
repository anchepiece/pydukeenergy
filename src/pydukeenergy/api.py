import logging
import json
import sys

from bs4 import BeautifulSoup
import requests

from pydukeenergy.meter import meter

BASE_URL = "https://www.duke-energy.com/"
LOGIN_URL = BASE_URL + "form/Login/GetAccountValidationMessage"
USAGE_ANALYSIS_URL = BASE_URL + "api/UsageAnalysis/"
BILLING_INFORMATION_URL = USAGE_ANALYSIS_URL + "GetBillingInformation"
METER_ACTIVE_URL = BASE_URL + "my-account/usage-analysis"
USAGE_CHART_URL = USAGE_ANALYSIS_URL + "GetUsageChartData"

USER_AGENT = {"User-Agent": "python/{}.{} pyduke-energy/0.0.1"}
LOGIN_HEADERS = {"Content-Type": "application/x-www-form-urlencoded"}
USAGE_ANALYSIS_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/plain, */*"}

_LOGGER = logging.getLogger(__name__)


class DukeEnergy(object):
    """
    API interface object.
    """

    def __init__(self, email, password):
        """
        Create the Duke Energy API interface object.
        Args:
            email (str): Duke Energy account email address.
            password (str): Duke Energy account password.
        """
        global USER_AGENT
        version_info = sys.version_info
        major = version_info.major
        minor = version_info.minor
        USER_AGENT["User-Agent"] = USER_AGENT["User-Agent"].format(major, minor)
        self.email = email
        self.password = password
        self.meters = []
        self.session = requests.Session()
        self._login()

    def get_meters(self):
        return self.meters

    def _get_billing_info(self, meter):
        """
        Pull a water heater's usage report from the API.
        """
        post_body = {"MeterNumber": meter.type + " - " + meter.id}
        headers = USAGE_ANALYSIS_HEADERS.copy()
        headers.update(USER_AGENT)
        response = self.session.post(BILLING_INFORMATION_URL, data=json.dumps(post_body), headers=headers, timeout=10, verify=False)
        if response.status_code != 200:
            _LOGGER.error("Failed to get billing info")
            return None
        if response.json()["Status"] == "ERROR":
            _LOGGER.error(response.json()["ErrorMsg"])
            return None
        return meter.set_billing_usage(response.json()["Data"][-1])

    def _get_usage_chart_data(self, meter):
        """
        billing_frequency ["Week", "Billing Cycle", "Month"]
        graph ["hourlyEnergyUse", "DailyEnergy", "averageEnergyByDayOfWeek"]
        """
        post_body = {"Graph": "DailyEnergy", "BillingFrequency": "Week", "GraphText": "Daily Energy and Avg. "}
        post_body["Date"] = meter.date.strftime("%m / %d / %Y")
        post_body["MeterNumber"] = meter.type + " - " + meter.id
        post_body["ActiveDate"] = meter.start_date
        headers = USAGE_ANALYSIS_HEADERS.copy()
        headers.update(USER_AGENT)
        response = self.session.post(USAGE_CHART_URL, data=json.dumps(post_body), headers=headers, timeout=10, verify=False)
        if response.status_code != 200:
            _LOGGER.error("Failed to get billing info")
            return None
        if response.json()["Status"] == "ERROR":
            _LOGGER.error(response.json()["ErrorMsg"])
            return None
        return meter.set_chart_usage(response.json())

    def _login(self):
        """
        Authenticate.
        """
        data = {"userId": self.email, "userPassword": self.password, "deviceprofile": "mobile"}
        headers = LOGIN_HEADERS.copy()
        headers.update(USER_AGENT)
        response = self.session.post(LOGIN_URL, data=data, headers=headers, timeout=10, verify=False)
        if response.status_code != 200:
            return False
        self._get_meters()

    def _get_meters(self):
        """
        There doesn't appear to be a service to get this data.
        Collecting the meter info to build meter objects.
        """
        response = self.session.get(METER_ACTIVE_URL, timeout=10, verify=False)
        soup = BeautifulSoup(response.text, "html.parser")
        meter_data = json.loads(soup.find("duke-dropdown", {"id": "meter"})["items"])
        for ameter in meter_data:
            meter_type, meter_id = ameter["text"].split(" - ")
            meter_start_date = ameter["CalendarStartDate"]
            self.meters.append(meter(self, meter_type, meter_id, meter_start_date))



