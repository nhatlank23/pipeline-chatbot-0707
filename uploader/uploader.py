"""
Module hỗ trợ tải (upload) các file Markdown lên OpenAI Vector Store và quản lý Vector Store.
"""

def upload_file_to_openai(file_path: str, openai_api_key: str) -> str:
    """
    Tải một file đơn lẻ lên OpenAI Files API.
    
    Args:
        file_path: Đường dẫn tới file markdown cần upload.
        openai_api_key: API Key của OpenAI.
        
    Returns:
        Mã ID của file trên OpenAI (OpenAI File ID).
    """
    # TODO: Triển khai logic upload file lên OpenAI Files API
    return ""

def add_file_to_vector_store(file_id: str, vector_store_id: str, openai_api_key: str) -> bool:
    """
    Thêm một File ID vào OpenAI Vector Store được chỉ định.
    
    Args:
        file_id: Mã ID của file trên OpenAI.
        vector_store_id: Mã ID của Vector Store đích.
        openai_api_key: API Key của OpenAI.
        
    Returns:
        True nếu thêm thành công, ngược lại là False.
    """
    # TODO: Triển khai liên kết file với Vector Store
    return True

def delete_file_from_vector_store(file_id: str, vector_store_id: str, openai_api_key: str) -> bool:
    """
    Xóa một file khỏi Vector Store và xóa hẳn file đó trên hệ thống OpenAI.
    
    Args:
        file_id: Mã ID của file trên OpenAI.
        vector_store_id: Mã ID của Vector Store.
        openai_api_key: API Key của OpenAI.
        
    Returns:
        True nếu xóa thành công, ngược lại là False.
    """
    # TODO: Triển khai logic dọn dẹp và xóa file cũ trên OpenAI
    return True

def run_uploader(files_to_upload: list[str], files_to_delete: list[str], vector_store_id: str, openai_api_key: str):
    """
    Điều phối việc tải lên (upload) và xóa (delete) các file trong OpenAI Vector Store.
    
    Args:
        files_to_upload: Danh sách đường dẫn các file markdown cần tải lên/cập nhật.
        files_to_delete: Danh sách các OpenAI File ID hoặc đường dẫn cần xóa.
        vector_store_id: Mã ID của OpenAI Vector Store.
        openai_api_key: API Key của OpenAI.
    """
    # TODO: Thực hiện các tác vụ upload và delete
    pass
