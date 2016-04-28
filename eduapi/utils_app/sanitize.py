import bleach
import string


#default options for bleach.clean:
DEFAULTS_CLEAN = {

    # ALLOWED_TAGS
    'tags': [
        'b', 'i', 'u', 's',  #styling
        'sub', 'sup',  #extra styling
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'h7',  #headings
        'ol', 'ul', 'li',  #lists
        'p', 'br', 'hr', 'pre',  #lines and paragraphs
        'span', 'div',  #spans and divs
        'em', 'strong', 'cite', 'dfn', 'code', 'samp', 'kbd', 'var', 'abbr', 'acronym',   #phrases
        'blockquote', 'q',  #quatations
        'del', 'ins',  #marking document changes
        'dd', 'dl', 'dt', 'dir', 'menu',  #defintion list
        'a',  #links
        # 'img',  #images
    ],

    # ALLOWED_ATTRIBUTES
    'attributes': {
        '*': ['dir',],
        'a': ['href', 'target', 'title',],
        'img': ['src', 'alt', 'width', 'height',],
    },

    # ALLOWED STYLES:
    'styles': [
    ],

    # Remove not allowed tags:
    'strip': True,

    # Remove HTML comments:
    'strip_comments': True,

}


def sanitize_html(html, options=None):
    '''
    Cleans the HTML according to the given options based on DEFAULTS_CLEAN options.

    :param html: HTML string.
    :param options: dictionary for bleach.clean function (using DEFAULTS_CLEAN).
    :return: cleaned HTML.
    '''
    #make options based on defaults:
    options = options if options is not None else {}
    options = dict(DEFAULTS_CLEAN, **options)

    #return cleaned HTML:
    return bleach.clean(html, **options)

def sanitize_string(unsanitized_string):

    valid_chars = "-_.() %s%s" % (string.ascii_letters, string.digits)
    return ''.join(c for c in unsanitized_string if c in valid_chars)

