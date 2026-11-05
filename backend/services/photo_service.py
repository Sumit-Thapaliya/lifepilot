def extract_photo(path):
    try:
        import pytesseract
        from PIL import Image
        text=pytesseract.image_to_string(Image.open(path)).strip()
    except Exception: text=''
    return {'text':text,'needs_confirmation':True}
def extract_tasks_from_photo(content, filename, approved=False):
    import tempfile, os
    fd,path=tempfile.mkstemp(suffix=os.path.splitext(filename)[1] or '.png')
    try:
        with os.fdopen(fd,'wb') as f:f.write(content)
        return {**extract_photo(path),'approved':approved,'filename':filename}
    finally:
        try: os.unlink(path)
        except OSError: pass
extract_photo_text = extract_photo
