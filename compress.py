#!/usr/bin/env python

import sys,time,bisect
from collections import OrderedDict

#~ BLACKLIST = []
BLACKLIST = ['\n',' ']
MIN_WORD = 6
MAX_WORD_BITS = 4
MIN_COUNT = 2
VERBOSE = False
DEBUG = False
DEFAULT_ESCAPE = '\\'

MAX_WORD = 2**MAX_WORD_BITS
MAX_REL_BITS = 16-MAX_WORD_BITS
MAX_REL = 2**MAX_REL_BITS

def compress(instr):

  escape = DEFAULT_ESCAPE
  count = instr.count(escape)
  for i in range(0,256):
    if count==0:
      break
    c = chr(i)
    found = instr.count(c)
    if found<count:
      escape = c
      count = found

  print 'Chose escape %s (found %s times)' % (hex(ord(escape)),count)

  s = instr.replace(escape,'')

  tic = time.time()
  replace = OrderedDict()
  i = 0
  done = len(s)-(MIN_COUNT+1)*MIN_WORD
  while i<done:
    sys.stdout.write('Building dictionary... %.2f%%\r' % (100.0*i/done))
    for l in range(MAX_WORD+MIN_WORD-1,MIN_WORD-1,-1):
      word = s[i:i+l]
      skip = False
      for x in BLACKLIST:
        if x in word:
          skip = True
          break
      if skip:
        continue
      if word in replace:
        #i += len(word)-1
        break
      replace[word] = s.count(word)
      #~ if replace[word]>MIN_COUNT:
        #~ i += len(word)-1
        #~ break
    i += 1
  print 'Building dictionary... 100.00%'

  print 'Search took %s sec' % (time.time()-tic)
  print 'Dictionary has %s words (file was %s characters)' % (len(replace),len(s))

  tic = time.time()
  replace = [(k,v) for (k,v) in replace.items() if v>MIN_COUNT]
  replace = sorted(replace,key=lambda a:a[1]*(len(a[0])-3),reverse=True)

  print 'Found %s words that appeared at least %s times' % (len(replace),MIN_COUNT+1)
  print 'Sorting took %s sec' % (time.time()-tic)
  if VERBOSE:
    print '\n'.join(['%5s "%s"' % (v,k.replace('\n','\\n')) for (k,v) in replace[:10]])

  tic = time.time()
  index = []
  for (i,(word,_)) in enumerate(replace):
    sys.stdout.write('Indexing... %.2f%%\r' % (100.0*i/len(replace)))
    matches = get_matches(s,word)
    for match in matches:
      index.append((word,match))
  print 'Indexing... 100.00%'
  print 'Sorting...'
  index = sorted(index,key=lambda a:a[1]-len(a[0])/2.0/MAX_WORD)
  print 'Indexing took %s sec' % (time.time()-tic)

  if VERBOSE:
    print '\n'.join(['%5s %s' % (i,word.replace('\n','\\n')) for (word,i) in index[:10]])

  tic = time.time()
  replaced = 0
  offset = 0
  first = {}
  last = -1
  for (j,(word,i)) in enumerate(index):

    sys.stdout.write('Replacing... %.2f%%\r' % (100.0*j/len(index)))

    if i<last:
      continue

    i -= offset
    length = len(word)

    f = first.get(word,None)
    if f is None:
      if s[i:i+length]==word:
        first[word] = i
      continue

    # TODO: figure out why this check is necessary
    original = s[f:f+length]
    if original!=word or original!=s[i:i+length]:
      continue

    rel = i-f
    if rel>MAX_REL-1:
      first[word] = i
      continue

    if DEBUG:
      print 'first = "%s"' % s[f:f+length].replace('\n','\\n')
      print 'word  = "%s"' % word.replace('\n','\\n')
      print ('%s = %s' % ((f,f+length),(i,i+length)))
      print s[f:f+length].replace('\n','\\n')
      print s[i:i+length].replace('\n','\\n')
    s = s[:i]+escape+encode(rel,length)+s[i+length:]
    if DEBUG:
      print '-'*20
      print s
      print '='*40
    last = i+length
    offset += (length-3)
    replaced += 1

  print 'Replacing... 100.00%'
  print 'Replaced %s words in %s sec' % (replaced,time.time()-tic)

  return escape+s

def decompress(outstr):

  escape = outstr[0]
  s = outstr[1:]

  i = len(s)-2
  while i>=0:
    if s[i]==escape:
      (rel,length) = decode(s[i+1:i+3])
      s = s[:i]+s[i-rel:i-rel+length]+s[i+3:]
      if DEBUG:
        print ('%s:%s = "%s"'
            % (i-rel,i-rel+length,s[i-rel:i-rel+length].replace('\n','\\n')))
        print '-'*20
        print s
        print '='*40
    i -= 1

  return s

def get_matches(s,word):

  matches = []
  i = 0
  while i<len(s)-len(word):
    if s[i:i+len(word)]==word:
      matches.append(i)
      i += len(word)
    else:
      i += 1
  return matches

def encode(rel,length):

  if DEBUG:
    print (rel,length)
  rel = bin(rel)[2:].zfill(MAX_REL_BITS)
  length = bin(length-MIN_WORD)[2:].zfill(MAX_WORD_BITS)
  full = rel+length
  if DEBUG:
    print full
  return chr(int(full[:8],2))+chr(int(full[8:],2))

def decode(s):

  s = bin(ord(s[0]))[2:].zfill(8)+bin(ord(s[1]))[2:].zfill(8)
  rel = int(s[:MAX_REL_BITS],2)
  length = int(s[MAX_REL_BITS:],2)+MIN_WORD
  return (rel,length)

class Document(object):

  def __init__(self,length):

    self.length = length
    self.matches = []
    self.protected = Range(length)
    self.offset = 0

  def add_match(self,match):

    for m in self.matches:
      if match.intersects(m):
        return False

    r = Range(self.length,(match.found_start,match.found_end))
    if r.intersects(self.protected):
      return False

    bisect.insort(self.matches,match)
    self.protected += Range(self.length,(match.ref_start,match.ref_end))
    return True

class Match(object):

  def __init__(self,ref,length,found):

    self.ref_start = ref
    self.ref_end = ref+length-1
    self.found_start = found
    self.found_end = found+length-1

  def __lt__(self,other):

    if not isinstance(other,Match):
      raise TypeError
    return self.found_start<other.found_start

  def intersects(self,other):

    if not isinstance(other,Match):
      raise TypeError
    return (
      self.found_start<other.found_end and self.found_end>other.found_start
    )

  def __str__(self):

    return ('%s:%s = %s:%s'
        % (self.found_start,self.found_end,self.ref_start,self.ref_end))

  __repr__ = __str__

class Range(object):

  def __init__(self,length,start=None):

    self.length = length
    if start is None:
      self.ranges = []
    elif isinstance(start,tuple):
      self.ranges = [start]
    elif isinstance(start,list):
      self.ranges = start
    else:
      raise TypeError

  def intersects(self,other):

    if not isinstance(other,Range):
      raise TypeError

    for (s1,e1) in self.ranges:
      for (s2,e2) in other.ranges:
        if s1<e2 and e1>s2:
          return True

  def copy(self):

    new = Range(self.length)
    new.ranges = [x for x in self.ranges]
    return new

  def __contains__(self,other):

    if not isinstance(other,int):
      raise TypeError

    return self.intersects(Range(self.length,(other,other)))

  def __add__(self,other):

    if not isinstance(other,Range):
      return NotImplemented

    if self.length!=other.length:
      return ValueError

    new = self.copy()

    for (s2,e2) in other.ranges:
      right = len(new.ranges)
      inter = []
      for (i,(s1,e1)) in enumerate(new.ranges):
        if e2<s1:
          right = i
        if s1<e2 and e1>s2:
          inter.append(i)
      if inter:
        s = min(new.ranges[inter[0]][0],s2)
        e = max(new.ranges[inter[-1]][1],e2)
        del new.ranges[inter[0]:inter[-1]+1]
      else:
        (s,e) = (s2,e2)
      new.ranges.insert(right,(s,e))

    return new

  def __str__(self):

    result = ['-']*self.length
    for (s,e) in self.ranges:
      result[s:e+1] = ['#']*(e-s+1)
    return ''.join(result)

if __name__=='__main__':

  tic = time.time()

  with open(sys.argv[1],'rb') as f:
    s = f.read()
  inlen = len(s)

  if sys.argv[2]=='c':
    s = compress(s)
  elif sys.argv[2]=='d':
    s = decompress(s)
  else:
    raise RuntimeError('invalid option "%s"' % sys.argv[2])
  with open(sys.argv[3],'wb') as f:
    f.write(s)
  outlen = len(s)

  print ''
  print '%sompressing took %s sec' % (['Dec','C'][sys.argv[2]=='c'],time.time()-tic)
  print '(out %s) / (in %s) = %s%%\n' % (outlen,inlen,100*outlen/inlen)
