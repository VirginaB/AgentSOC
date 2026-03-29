import csv
import io
from pathlib import Path


TEXT_EXTENSIONS = {".txt", ".log", ".out", ".jsonl"}
CSV_EXTENSIONS = {".csv", ".tsv"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | CSV_EXTENSIONS
DEFAULT_LOG_COLUMNS = (
    "log",
    "log_text",
    "message",
    "msg",
    "event",
    "content",
    "raw",
)


def parse_uploaded_logs(filename: str, content: bytes) -> list[dict]:
    ext = Path(filename or "").suffix.lower()
    text = _decode_content(content)

    if ext in CSV_EXTENSIONS:
        return _parse_delimited_file(text, ext)

    if ext in TEXT_EXTENSIONS or ext == "":
        return _parse_line_based_file(text)

    raise ValueError(f"Unsupported file type: {ext or 'unknown'}")


def _decode_content(content: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Unable to decode uploaded file.")


def _parse_line_based_file(text: str) -> list[dict]:
    logs = []
    for line in text.splitlines():
        log_text = line.strip()
        if not log_text:
            continue
        logs.append({"log_text": log_text, "source_ip": None})
    return logs


def _parse_delimited_file(text: str, ext: str) -> list[dict]:
    delimiter = "\t" if ext == ".tsv" else _detect_delimiter(text)
    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)

    if not reader.fieldnames:
        raise ValueError("CSV file does not contain a header row.")

    normalized = {field.lower().strip(): field for field in reader.fieldnames if field}
    log_column = next((normalized[name] for name in DEFAULT_LOG_COLUMNS if name in normalized), None)
    ip_column = normalized.get("source_ip") or normalized.get("src_ip") or normalized.get("ip")

    if not log_column:
        raise ValueError(
            "CSV upload requires a log column such as log, log_text, message, event, or raw."
        )

    logs = []
    for row in reader:
        raw_value = row.get(log_column)
        log_text = raw_value.strip() if isinstance(raw_value, str) else ""
        if not log_text:
            continue

        source_ip = None
        if ip_column:
            ip_value = row.get(ip_column)
            if isinstance(ip_value, str):
                source_ip = ip_value.strip() or None

        logs.append({"log_text": log_text, "source_ip": source_ip})

    return logs


def _detect_delimiter(text: str) -> str:
    sample = "\n".join(text.splitlines()[:5])
    if not sample.strip():
        return ","

    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","
