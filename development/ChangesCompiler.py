import difflib
import os
import shutil
import zipfile
import requests  # type: ignore
import json
import re


class CamsToolUpdater:
    def __init__(self, script_folder=None, cams_version=None):
        self.versions_folder = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "versions",
        )
        self.script_folder = script_folder

        self.index = None

        if cams_version:
            self.cams_version = cams_version
        else:
            self.index = -1

            import aleha_tools  # type: ignore

            self.cams_version = aleha_tools.DATA["VERSION"]

        self.tmpFolder = os.path.join(os.environ["TEMP"], "cams_tmp")
        self.tmpScriptFolder = os.path.join(self.tmpFolder, "aleha_tools")
        self.changes_folder = os.path.join(self.tmpFolder, "changes")
        self.base_url = "https://api.groq.com/openai/v1"
        self.api_key = "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"
        self.model = "llama3-8b-8192"  # 'llama-3-8b-instruct' # "gpt-4o-mini" # "llama-3-70b-instruct" # gemini-pro
        self.all_changes = {}

    def complete_chat(self, message):
        endpoint = "/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": message}],
        }
        try:
            response = requests.post(
                self.base_url + endpoint, json=payload, headers=headers
            )
            response.raise_for_status()  # Raise an exception for HTTP errors
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API Request Failed: {e}")
            return None

    def download_latest_version(self):
        if os.path.exists(self.tmpFolder):
            shutil.rmtree(self.tmpFolder)

        for f in [self.tmpFolder, self.changes_folder]:
            os.mkdir(f)

        all_version_files = sorted(os.listdir(self.versions_folder))

        latest_file = all_version_files[-1]
        if not self.index and os.path.splitext(latest_file)[0].endswith(
            str(self.cams_version)
        ):
            latest_file = all_version_files[-2]

        latest_file_path = os.path.join(self.versions_folder, latest_file)

        tmpZipFile = os.path.join(self.tmpFolder, latest_file)
        output = shutil.copy(latest_file_path, tmpZipFile)

        zfobj = zipfile.ZipFile(tmpZipFile)
        for name in zfobj.namelist():
            uncompressed = zfobj.read(name)
            filename = os.path.join(self.tmpFolder, name)
            if os.path.isdir(filename):
                continue
            d = os.path.dirname(filename)
            if not os.path.exists(d):
                os.mkdir(d)
            output = open(filename, "wb")
            output.write(uncompressed)
            output.close()
        zfobj.close()
        if os.path.isfile(tmpZipFile):
            os.remove(tmpZipFile)

    def analyze_changes(self):
        for root, subfolders, files in os.walk(self.tmpScriptFolder):
            for file in files:
                if not file.endswith(".py"):
                    continue

                tmp_path = os.path.join(root, file)
                relative_path = os.path.relpath(tmp_path, self.tmpScriptFolder)
                current_path = os.path.join(self.script_folder, relative_path)

                with open(tmp_path, "r", encoding="utf-8", errors="replace") as source:
                    with open(
                        current_path, "r", encoding="utf-8", errors="replace"
                    ) as endpoint:
                        diff = difflib.unified_diff(
                            source.readlines(),
                            endpoint.readlines(),
                            fromfile="%s (old)" % file,
                            tofile="%s (new)" % file,
                        )

                        changes = list(diff)
                        if (
                            changes
                        ):  # If there are changes, write them to the changes log
                            self.all_changes[file] = changes
                            changes_file = os.path.join(
                                self.changes_folder,
                                os.path.splitext(relative_path)[0] + ".txt",
                            )
                            changes_path = os.path.dirname(changes_file)
                            if not os.path.isdir(changes_path):
                                os.mkdir(changes_path)
                            with open(
                                changes_file, "w", encoding="utf-8"
                            ) as changes_log:
                                for line in changes:
                                    changes_log.write(line)

    def generate_changelog(self):
        formatted_changes = "\n".join(
            [
                "\n" + file + "\n" + "".join(changes)
                for file, changes in self.all_changes.items()
            ]
        )

        # Truncate the input to a maximum length (e.g., 10,000 characters)
        max_length = 10000
        if len(formatted_changes) > max_length:
            formatted_changes = (
                formatted_changes[:max_length] + "\n\n... (truncated due to size)"
            )

        prompt = f"Make a simple changelog up to 4 lines of 30 characters each. Add an 'And more...' if there are too many. Format it like a Python list, for example: ['change.', 'change.', 'change.', 'change.']:\n\n{formatted_changes}"

        gpt_log_file = os.path.join(self.tmpFolder, "gpt_log.txt")
        if os.path.isfile(gpt_log_file):
            os.remove(gpt_log_file)
        with open(gpt_log_file, "w", encoding="utf-8") as gpt_log:
            gpt_log.write(prompt + "\n\n\n\n")

        response = self.complete_chat(prompt)

        if response is None:
            print("API request failed. Check logs for details.")
            return ["API request failed. Check logs for details."]

        with open(gpt_log_file, "a", encoding="utf-8") as gpt_log:
            json.dump(response, gpt_log, indent=4)

        try:
            changelog = eval(response["choices"][0]["message"]["content"])
        except Exception:
            changelog = response["choices"][0]["message"]["content"]

        if isinstance(changelog, str):
            changelog = re.findall(r"'(.*?)'", changelog)

        try:
            for index, change in enumerate(changelog):
                if change.endswith(","):
                    changelog[index] = change[:-1]
                if not change.endswith("."):
                    changelog[index] += "."
        except Exception as e:
            print(f"Error formatting changelog: {e}")

        return changelog

    def run(self):
        self.download_latest_version()
        self.analyze_changes()
        changelog = self.generate_changelog()
        return changelog


if __name__ == "__main__":
    updater = CamsToolUpdater()
    changelog = updater.run()
