import re
import hashlib
from bson import ObjectId
from datetime import datetime


def string_conversation(conversation):
    n = 0
    _str_conversation_ = ''
    for msn in conversation:
        if n % 2 == 0:
            _str_conversation_ += 'Human:'+msn.content+'\n'
            n += 1
        else:
            _str_conversation_ += 'AI:'+msn.content+'\n'
            n += 1

    return '\n'.join(_str_conversation_.split('\n')[-9:])


def setting_cellphone(number):
    number = str(number)
    # It is a mexican number
    if str(number)[0:2] == '52':
        number = '52'+number[3:]
    else:
        number = str(number)
    return number


def split_by_dot_except_links(input_str):
    parts = []
    start = 0  # Starting index of each substring
    in_link = False  # True if the current position is inside a link

    for i, c in enumerate(input_str):
        if input_str[i:i+7] == 'http://' or input_str[i:i+8] == 'https://':
            in_link = True  # Start of a link detected

        if in_link and c == ' ':
            in_link = False  # End of a link detected

        if c == '.' and not in_link:
            parts.append(input_str[start:i+1].strip())
            start = i + 1  # Update the start index for the next substring

    if start < len(input_str):  # Add the last remaining substring
        parts.append(input_str[start:].strip())

    parts = list(filter(lambda item: item != "", parts))

    return parts


def remove_dots_commas(frase):
    # Utiliza una expresión regular para eliminar puntos y comas
    frase_sin_puntos_comas = re.sub(r'[.]', '', frase)
    return frase_sin_puntos_comas


def restore_urls_in_phrase(phrase, urls):
    # Restaura las URLs en la frase
    for i, url in enumerate(urls):
        phrase = phrase.replace(f'_URL_{i}_', url)

    return phrase


def is_url(phrase):
    # Expresión regular para verificar si la frase es una URL
    url_pattern = r'^(https?://|www\.)\S+'

    # Comprueba si la frase coincide con el patrón de URL
    return re.match(url_pattern, phrase) is not None


def remove_last_points(frase):
    # Utiliza una expresión regular para eliminar los puntos al final de la frase
    frase_sin_puntos = re.sub(r'\.{2,}$', '', frase)
    return frase_sin_puntos


def split_last_question(text):
    match = re.search("[¿]", text)
    return [text[:match.start()], text[match.start():]] if match else text


def split_paragraphs(texto):
    parrafos = re.split(r'\s*\n\s*', texto)

    # Post-procesar para unir párrafos divididos erróneamente por abreviaturas
    i = 0
    while i < len(parrafos) - 1:
        if parrafos[i].endswith(('Dr.', 'Mr.', 'Ms.', 'Sr.', 'Sra.', 'St.')):
            parrafos[i] = parrafos[i] + " " + parrafos[i+1]
            del parrafos[i+1]
        else:
            i += 1
    parrafos[-1] = split_last_question(parrafos[-1])
    parrafos = [item for sublist in parrafos for item in (
        sublist if isinstance(sublist, list) else [sublist])]

    return [p for p in parrafos if p.strip()]


def remove_after_last_semicolon(text):
    # Split the text into parts using ';' as the delimiter, starting from the end
    parts = text.rsplit(';', 1)

    # Return the first part (before the last ';')
    return parts[0].strip() if len(parts) > 1 else text.strip()


def default_bson(obj):
    from bson import ObjectId
    if isinstance(obj, ObjectId):
        return str(obj)
    raise TypeError("Object of type %s is not JSON serializable" %
                    type(obj).__name__)


def generate_unique_id(string1, string2):
    # Combine the strings
    combined_string = string1 + string2

    # Create a SHA-256 hash of the combined string
    hash_obj = hashlib.sha256(combined_string.encode())

    # Get the hexadecimal representation of the hash
    hex_digest = hash_obj.hexdigest()

    # Use the first 24 characters of the hash to create a MongoDB ObjectId
    # Note: This may not be a valid ObjectId if it doesn't conform to ObjectId specifications
    mongoid = ObjectId(hex_digest[:24])

    return mongoid


def get_datetime():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
