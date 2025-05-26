import os

def read_amount_from_file(filepath="amount.txt"): # Added default for easier testing
    """Reads amount from the specified file."""
    try:
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            with open(filepath, 'r', encoding='utf-8') as f: # Specify encoding
                content_raw = f.read()
                print(f"Raw content from file: '{content_raw}' (repr: {repr(content_raw)})")

                content_stripped = content_raw.strip()
                print(f"Stripped content: '{content_stripped}' (repr: {repr(content_stripped)})")

                # Handle common issues:
                # 1. Remove thousands separators (commas if dot is decimal, or dots if comma is decimal)
                #    Assuming dot is the decimal separator for now, so remove commas.
                content_processed = content_stripped.replace(',', '')

                # If you suspect commas are used as decimal separators (e.g., "123,45")
                # AND you've already removed thousands separators if they were dots:
                # content_processed = content_processed.replace(',', '.')

                print(f"Content after potential replacements: '{content_processed}' (repr: {repr(content_processed)})")

                if not content_processed: # If after stripping/replacing, it's empty
                    print("Content became empty after processing.")
                    return None

                # Attempt to convert to float
                amount_float = float(content_processed)
                return str(amount_float) # Return as string as per original code
        else:
            if not os.path.exists(filepath):
                print(f"File '{filepath}' does not exist.")
            elif os.path.getsize(filepath) == 0:
                print(f"File '{filepath}' is empty.")
            return None
    except ValueError as e:
        print(f"ValueError: Could not convert content to float. Content was '{content_processed if 'content_processed' in locals() else 'N/A'}'. Error: {e}")
        return None
    except IOError as e:
        print(f"IOError reading file '{filepath}': {e}")
        return None
    except Exception as e: # Catch any other unexpected errors
        print(f"An unexpected error occurred: {e}")
        return None
print(read_amount_from_file("amount.txt"))