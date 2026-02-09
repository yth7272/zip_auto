# ==========================================
# [시트 핸들러] Google Sheets 읽기/쓰기
# ==========================================

import re
import gspread
from google.oauth2.service_account import Credentials

from config import SERVICE_ACCOUNT_FILE, SERVICE_ACCOUNT_INFO

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_credentials():
    """로컬은 파일, Streamlit Cloud는 secrets에서 인증"""
    if SERVICE_ACCOUNT_FILE:
        return Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    return Credentials.from_service_account_info(SERVICE_ACCOUNT_INFO, scopes=SCOPES)


def connect_sheet(sheet_url: str, worksheet_name: str = None):
    """
    Google Sheets에 서비스 계정으로 연결합니다.

    Args:
        sheet_url: 스프레드시트 URL
        worksheet_name: 워크시트 이름 (None이면 첫 번째 시트)

    Returns:
        tuple: (gspread.Worksheet, gspread.Spreadsheet)
    """
    creds = _get_credentials()
    gc = gspread.authorize(creds)

    spreadsheet = gc.open_by_url(sheet_url)

    if worksheet_name:
        worksheet = spreadsheet.worksheet(worksheet_name)
    else:
        worksheet = spreadsheet.sheet1

    return worksheet, spreadsheet


def get_worksheet_names(sheet_url: str) -> list:
    """스프레드시트의 모든 워크시트 이름 반환"""
    creds = _get_credentials()
    gc = gspread.authorize(creds)
    spreadsheet = gc.open_by_url(sheet_url)
    return [ws.title for ws in spreadsheet.worksheets()]


def read_sheet_preview(worksheet, max_rows=20) -> list:
    """
    시트의 미리보기 데이터를 가져옵니다.

    Args:
        worksheet: gspread Worksheet 객체
        max_rows: 최대 행 수

    Returns:
        list[list]: 2D 배열 (헤더 포함)
    """
    all_values = worksheet.get_all_values()
    return all_values[:max_rows] if len(all_values) > max_rows else all_values


def read_all_data(worksheet) -> list:
    """시트의 전체 데이터를 가져옵니다."""
    return worksheet.get_all_values()


def get_column_index(header_row: list, column_name: str) -> int:
    """
    헤더 행에서 column 이름의 인덱스를 반환합니다 (0-based).

    Args:
        header_row: 헤더 행 리스트
        column_name: 찾을 column 이름

    Returns:
        int: 인덱스 (못 찾으면 -1)
    """
    for i, h in enumerate(header_row):
        if h.strip() == column_name.strip():
            return i
    return -1


def find_empty_zipcode_rows(all_data: list, addr_col_idx: int, zip_col_idx: int) -> list:
    """
    주소가 있고 우편번호가 비어있는 행들을 찾습니다.

    Args:
        all_data: 전체 시트 데이터 (헤더 포함)
        addr_col_idx: 주소 column 인덱스
        zip_col_idx: 우편번호 column 인덱스

    Returns:
        list[dict]: [{row_num(1-based), address}, ...]
    """
    rows_to_process = []

    for i, row in enumerate(all_data):
        if i == 0:  # 헤더 스킵
            continue

        # column 범위 체크
        address = row[addr_col_idx].strip() if addr_col_idx < len(row) else ""
        zipcode = row[zip_col_idx].strip() if zip_col_idx < len(row) else ""

        if address and not zipcode:
            rows_to_process.append({
                "row_num": i + 1,  # gspread는 1-based
                "address": address,
            })

    return rows_to_process


def write_results(worksheet, results: list, zip_col_idx: int, acc_col_idx: int):
    """
    결과를 시트에 일괄 기록합니다.

    Args:
        worksheet: gspread Worksheet 객체
        results: [{row_num, zipcode, accuracy}, ...]
        zip_col_idx: 우편번호 column 인덱스 (0-based)
        acc_col_idx: 정확도 column 인덱스 (0-based)
    """
    if not results:
        return

    # batch update로 효율적 기록
    cells_to_update = []

    for r in results:
        row_num = r["row_num"]
        # gspread cell 좌표는 (row, col) 1-based
        zip_cell = gspread.Cell(row_num, zip_col_idx + 1, value=r["zipcode"])
        cells_to_update.append(zip_cell)

        if acc_col_idx >= 0:
            acc_value = f'{r["accuracy"]}%'
            acc_cell = gspread.Cell(row_num, acc_col_idx + 1, value=acc_value)
            cells_to_update.append(acc_cell)

    worksheet.update_cells(cells_to_update, value_input_option="USER_ENTERED")
