from google.cloud import bigquery
from flask import Response

PROJECT_ID = "sonic-totem-469814-q5"
DATASET_ID = "transactions_dataset"
PREDICTION_TABLE = "transactions_predictions"

def suspicious_transactions(request):
    """
    Cloud Function (HTTP trigger).
    Renders suspicious transactions (predicted_is_valid = 0) from BigQuery as an HTML table.
    """

    try:
        bq = bigquery.Client()

        query = f"""
               SELECT transaction_id,
               entity_a,
               sector_a,
               entity_b,
               sector_b,
               transaction_amount,
               country_a,
               country_b,
               transaction_type,
               predicted_is_valid,
               probs.prob AS suspicious_probability
               FROM
              `{PROJECT_ID}.{DATASET_ID}.{PREDICTION_TABLE}` p,
               UNNEST(p.predicted_is_valid_probs) AS probs
               WHERE
               p.predicted_is_valid = 0
               AND probs.label = 0
               ORDER BY
               suspicious_probability DESC
               LIMIT 100
        """

        results = bq.query(query).result()
        rows = [dict(row) for row in results]

        # Build HTML table
        html = """
        <html>
        <head>
            <title>Suspicious Transactions</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                h2 { color: #cc0000; }
            </style>
        </head>
        <body>
            <h2>🚨 Suspicious Transactions</h2>
            <table>
                <tr>
        """

        if rows:
            # Add table headers
            for col in rows[0].keys():
                html += f"<th>{col}</th>"
            html += "</tr>"

            # Add table rows
            for row in rows:
                html += "<tr>"
                for val in row.values():
                    html += f"<td>{val}</td>"
                html += "</tr>"
        else:
            html += "<p>No suspicious transactions found ✅</p>"

        html += """
            </table>
        </body>
        </html>
        """

        return Response(html, mimetype="text/html")

    except Exception as e:
        return Response(f"<h3>Error: {str(e)}</h3>", mimetype="text/html")
