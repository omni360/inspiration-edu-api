import os, base64
import string, random

def generate_hash(length=40):
    '''
    Returns random hash code of the given length (using os.urandom to generate random bytes).
    '''
    urandom_length = (length * 3/4) + (1 if length % 4 else 0)
    hash = base64.urlsafe_b64encode(os.urandom(urandom_length))[:length]
    return hash

def generate_code(length, chars=string.ascii_letters+string.digits):
    rand = random.SystemRandom()
    code = ''.join(rand.choice(chars) for _ in xrange(length))
    return code
