import pytest
import requests
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


class TestPrism:
    @staticmethod
    def get_access_token():
        url = "https://prism.aighospitals.com:5786/token"
        payload = {
            'username': 'testuser',
            'password': 'testpassword'
        }
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        try:
            response = requests.post(url, data=payload, headers=headers)
            response.raise_for_status()
            token_data = response.json()
            print("✅ Token fetched successfully.")
            return token_data.get('access_token')
        except requests.RequestException as e:
            print("❌ Error fetching token:", e)
            return None

    @classmethod
    def setup_class(cls):
        cls.token = cls.get_access_token()
        if not cls.token:
            pytest.fail("❌ Token could not be retrieved.")
        cls.base_url = "https://prism.aighospitals.com:5786/process_audio"

    def test_post_audio_file(self):
            email_body = ""
            success = True

            headers = {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json, text/plain, */*",
                "Origin": "https://oneaig.aighospitals.com:4200",
                "Referer": "https://oneaig.aighospitals.com:4200/",
            }

            file_path = r"C:\Users\10013887\Automation_Projects\QA_PRISM\Project_Prism\audio_files\prism_audio_for_testing.wav"
            filename = os.path.basename(file_path)

            payload = {
                "operation_type": "generate",
                "section_ids": ["4", "1", "2", "7", "8", "3", "11", "9", "10", "14", "13", "6", "5", "12", "0014",
                                "0015", "0017"],
                "enable_native_transcript": False,
                "patient_id": "AIGG.20893625",
                "visit_id": "1514366",
                "name": "Mrs. REKHA  GUPTA",
                "doctor_id": "10009303",
                "doctor_name": "Dr. RAKESH KALAPALA (Med.Gastro)"
            }

            try:
                with open(file_path, "rb") as f:
                    files = {
                        "request": (None, json.dumps(payload), "application/json"),
                        "audio_file": (filename, f, "audio/wav")
                    }

                    response = requests.post(self.base_url, headers=headers, files=files, timeout=300)
                    assert response.status_code == 200, f"Expected 200 but got {response.status_code}"

                    try:
                        json_response = response.json()
                    except Exception as e:
                        print("❌ Response content:", response.text)
                        raise AssertionError(f"❌ Failed to parse JSON response: {e}")

                    # Validate top-level structure
                    if not json_response:
                        raise AssertionError("❌ Empty JSON response.")
                    ehr_data = json_response.get('ehr')
                    if not ehr_data:
                        raise AssertionError("❌ Missing 'ehr' in the response.")
                    summary_data = ehr_data.get('summary')
                    if not summary_data:
                        raise AssertionError("❌ Missing 'summary' in 'ehr' section.")

                    fields_to_check = [
                        ("Present Complaints", "present_complaints"),
                        ("Allergies", "Allergies"),
                        ("Family / Social / Immunization History", "Family_Social_Immunization_History_one"),
                        ("Diagnosis", "Diagnosis"),
                        ("Medications", "medications"),
                        ("Lab Orders", "Lab_Orders"),
                        ("Patient Medical History", "Patient_medical_History"),
                        ("Patient Surgical History", "Patient_Surgical_History"),
                        ("Systemic Examination", "Systemic_Examination"),
                        ("Previous Medications", "Previous_Medications"),
                        ("Diet / Physio Advice", "Diet_Physio_Advice"),
                        ("Plan of Care", "Plan_of_care"),
                    ]

                    for section, var_name in fields_to_check:
                        try:
                            section_data = json_response['ehr']['summary'].get(section)
                            if section_data and isinstance(section_data, list) and 'text' in section_data[0]:
                                value = section_data[0]['text']
                                email_body += f"{var_name}: {value}\n\n"
                            else:
                                email_body += f"{var_name}: ⚠️ Missing or malformed\n\n"
                        except Exception as e:
                            raise AssertionError(f"❌ Error processing section '{section}': {e}")

                    # Optional fields
                    try:
                        service = json_response['ehr']['metadata'].get('service_used', 'N/A')
                        transcription = json_response.get('transcription', 'N/A')
                        translation = json_response.get('translation', {}).get('text', 'N/A')

                        email_body += f"\nService Used: {service}\n"
                        email_body += f"\nTranscription Value: {transcription}\n"
                        email_body += f"\nRaw Conversation: {translation}\n"
                    except Exception as e:
                        raise AssertionError(f"❌ Failed to extract optional fields: {e}")

            except Exception as e:
                success = False
                email_body = f"❌ Test failed with error:\n{e}"

            finally:
                self.send_email_report(success, email_body)

    def send_email_report(self, success, body):
            from_email = "manikantha.ponduru@aighospitals.com"
            # Base recipients (always receive email)
            to_email_list = [
                "manikantha.ponduru@aighospitals.com",
                "krishnam.dantuluri@aighospitals.com",
                "challanandini@aighospitals.com"
            ]
            # Add these email only if test failed
            if not success:
                to_email_list.append("manikantha.ponduru@aighospitals.com")

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            subject = f"{'✅' if success else '❌'} Prism Test Report - {'Success' if success else 'Failed'} - {timestamp}"

            message = MIMEMultipart()
            message["From"] = from_email
            message["To"] = ", ".join(to_email_list)
            message["Subject"] = subject
            message.attach(MIMEText(body, "plain"))

            try:
                server = smtplib.SMTP("smtp.office365.com", 587)
                server.starttls()
                server.login(from_email, "mani@102515")  # ⚠️ Replace with app password or secure method
                server.sendmail(from_email, to_email_list, message.as_string())
                server.quit()
                print("📧 Email sent successfully via Outlook.")
            except Exception as e:
                print(f"❌ Failed to send email via Outlook: {e}")
