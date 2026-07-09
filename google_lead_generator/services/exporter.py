import os
import pandas as pd


class ExportService:

    def __init__(self):
        self.output_folder = "exports"
        os.makedirs(self.output_folder, exist_ok=True)

    def export_csv(self, df, filename="google_leads.csv"):

        file_path = os.path.join(self.output_folder, filename)

        df.to_csv(
            file_path,
            index=False,
            encoding="utf-8-sig"
        )

        return file_path

    def export_excel(self, df, filename="google_leads.xlsx"):

        file_path = os.path.join(self.output_folder, filename)

        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            df.to_excel(
                writer,
                index=False,
                sheet_name="Google Leads"
            )

        return file_path

    def export_all(self, df):

        return {
            "csv": self.export_csv(df),
            "excel": self.export_excel(df)
        }