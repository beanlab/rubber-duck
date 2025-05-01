import csv
import io
import zipfile


def zip_data_file(table_data):
    try:
        csv_buffer = io.StringIO()
        csv_writer = csv.writer(csv_buffer)

        csv_writer.writerows(table_data)

        csv_buffer.seek(0)
        csv_bytes = csv_buffer.getvalue().encode("utf-8")
        csv_buffer.close()

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr("data.csv", csv_bytes)

        zip_buffer.seek(0)
        return zip_buffer
    except Exception as e:
        print(f"Error exporting csvs: {e}")
        return None
