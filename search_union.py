#! /usr/bin/python3
# -*- coding: utf-8 -*-
#--------------------------------------------------------------------------------------------------
# Script to search a union dictionary
#
# Usage:
#   search_union.py [--data_prefix str] [--search str] [--view str] words...
#
# Example:
#   ./search_union.py --data_prefix union --search full --view full  united states
#
# Copyright 2020 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file
# except in compliance with the License.  You may obtain a copy of the License at
#     https://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software distributed under the
# License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
# either express or implied.  See the License for the specific language governing permissions
# and limitations under the License.
#--------------------------------------------------------------------------------------------------


import cgi
import html
import os
import regex
import sys
import tkrzw_dict
import tkrzw_union_searcher
import urllib


PAGE_WIDTH = 100
CGI_DATA_PREFIX = "union"
CGI_CAPACITY = 100
POSES = {
  "noun": "名",
  "verb": "動",
  "adjective": "形",
  "adverb": "副",
  "pronoun": "代名",
  "auxverb": "助動",
  "preposition": "前置",
  "determiner": "限定",
  "article": "冠",
  "interjection": "間投",
  "prefix": "接頭",
  "suffix": "接尾",
  "abbreviation": "省略",
  "misc": "他",
}
INFLECTIONS = [
  [("noun_plural", "複数")],
  [("verb_singular", "三単"),
   ("verb_present_participle", "現分"),
   ("verb_past", "過去"),
   ("verb_past_participle", "過分")],
  [("adjective_comparative", "形比"),
   ("adjective_superative", "形最")],
  [("adverb_comparative", "副比"),
   ("adverb_superative", "副最")]]
WORDNET_ATTRS = {
  "translation": "翻訳",
  "synonym": "同義",
  "antonym": "対義",
  "hypernym": "上位",
  "hyponym": "下位",
  "holonym": "全体",
  "meronym": "部分",
  "attribute": "属性",
  "derivative": "派生",
  "entailment": "随伴",
  "cause": "原因",
  "seealso": "参考",
  "group": "集合",
  "similar": "類義",
  "perticiple": "分詞",
  "pertainym": "関連",
  "topic": "話題",
  "region": "地域",
  "usage": "用法",
}
TEXT_ATTRS = {
  "可算": "c",
  "不可算": "u",
  "自動詞": "vi",
  "他動詞": "vt",
  "countable": "c",
  "uncountable": "u",
  "intransitive": "vi",
  "transitive": "vt",
}


def PrintWrappedText(text, indent):
  sys.stdout.write(" " * indent)
  width = indent
  foldable = True
  for c in text:
    if (foldable and width >= PAGE_WIDTH - 1) or width >= PAGE_WIDTH + 20:
      sys.stdout.write("\n")
      sys.stdout.write(" " * indent)
      width = indent
    sys.stdout.write(c)
    width += 2 if ord(c) > 256 else 1
    foldable = c == " "
  print("")
      

def PrintResult(entries, mode, query):
  for entry in entries:
    if mode != "list":
      print()
    title = entry.get("word")
    translations = entry.get("translation")
    if translations:
      if tkrzw_dict.PredictLanguage(query) != "en":
        translations = tkrzw_dict.TwiddleWords(translations, query)
      title += "  \"{}\"".format(", ".join(translations[:8]))
    elif mode == "list":
      for item in entry["item"]:
        text = item["text"].split(" [-] ")[0]
        title +=  "  \"{}\"".format(text)
        break
    if mode != "list":
      pron = entry.get("pronunciation")
      if pron:
        title += "  /{}/".format(pron)
    PrintWrappedText(title, 2)
    if mode == "full":
      for attr_list in INFLECTIONS:
        fields = []
        for name, label in attr_list:
          value = entry.get(name)
          if value:
            fields.append("{}: {}".format(label, value))
        if fields:
          PrintWrappedText("  ".join(fields), 4)
    if mode != "list":
      print()
    if mode in ("simple", "full"):
      num_items = 0
      for item in entry["item"]:
        if mode == "simple" and num_items >= 8:
          break
        label = item.get("label")
        pos = item.get("pos")
        sections = item["text"].split(" [-] ")
        text = ""
        if label:
          text += "({}) ".format(label)
        if pos:
          pos = POSES.get(pos) or pos
          text += "[{}] ".format(pos)
        text += sections[0]        
        PrintWrappedText(text, 4)
        if mode == "full":
          for section in sections[1:]:
            attr_match = regex.search(r"^\[([a-z]+)\]: ", section)
            if attr_match:
              if attr_match.group(1) == "synset": continue              
              attr_label = WORDNET_ATTRS.get(attr_match.group(1))
              if attr_label:
                section = "{}: {}".format(attr_label, section[len(attr_match.group(0)):].strip())
            subsections = section.split(" [--] ")
            PrintWrappedText(subsections[0], 6)
            for subsection in subsections[1:]:
              subsubsections = subsection.split(" [---] ")
              PrintWrappedText(subsubsections[0], 8)
              for subsubsubsection in subsubsections[1:]:
                PrintWrappedText(subsubsubsection, 10)
        num_items += 1
      if mode == "full":
        related = entry.get("related")
        if related:
          text = "[related] {}".format(", ".join(related[:8]))
          PrintWrappedText(text, 4)
        prob = entry.get("probability")
        if prob:
          text = "[prob] {:.4f}%".format(float(prob) * 100)
          PrintWrappedText(text, 4)
  if mode != "list":
    print()
  

def main():
  args = sys.argv[1:]
  data_prefix = tkrzw_dict.GetCommandFlag(args, "--data_prefix", 1) or "union"
  search_mode = tkrzw_dict.GetCommandFlag(args, "--search", 1) or "auto"
  view_mode = tkrzw_dict.GetCommandFlag(args, "--view", 1) or "auto"
  capacity = int(tkrzw_dict.GetCommandFlag(args, "--capacity", 1) or "100")
  query = " ".join(args)
  if not query:
    raise RuntimeError("words are not specified")
  if search_mode == "auto":
    if tkrzw_dict.PredictLanguage(query) == "en":
      search_mode = "exact"
    else:
      search_mode = "reverse"
  searcher = tkrzw_union_searcher.UnionSearcher(data_prefix)
  if search_mode == "exact":
    result = searcher.SearchExact(query)
  elif search_mode == "reverse":
    result = searcher.SearchReverse(query)
  elif search_mode == "related":
    result = searcher.SearchRelated(query, capacity)
  elif search_mode == "relrev":
    result = searcher.SearchRelatedReverse(query, capacity)
  else:
    raise RuntimeError("unknown search mode: " + search_mode)
  if result:
    if len(result) > capacity:
      result = result[:capacity]
    if view_mode == "auto":
      keys = searcher.GetResultKeys(result)
      if len(keys) < 2:
        view_mode = "full"
      elif len(keys) < 6:
        view_mode = "simple"
      else:
        view_mode = "list"
    if view_mode == "list":
      print()
    PrintResult(result, view_mode, query)    
    if view_mode == "list":
      print()
  else:
    print("No result.")


def esc(expr):
  if expr is None:
    return ""
  return html.escape(str(expr), True)


def P(*args, end="\n"):
  esc_args = []
  for arg in args[1:]:
    if isinstance(arg, str):
      arg = esc(arg)
    esc_args.append(arg)
  print(args[0].format(*esc_args), end=end)


def PrintResultCGI(entries, query, details):
  for entry in entries:
    P('<div class="entry">')
    word = entry["word"]
    word_url = "?q={}".format(urllib.parse.quote(word))
    P('<h2 class="entry_word"><a href="{}">{}</a></h2>', word_url, word)
    translations = entry.get("translation")
    if translations:
      if tkrzw_dict.PredictLanguage(query) != "en":
        translations = tkrzw_dict.TwiddleWords(translations, query)
      fields = []
      for tran in translations[:8]:
        tran_url = "?q={}".format(urllib.parse.quote(tran))
        value = '<a href="{}" class="tran">{}</a>'.format(esc(tran_url), esc(tran))
        fields.append(value)
      if fields:
        P('<div class="attr attr_tran">', end="")
        print(", ".join(fields), end="")
        P('</div>')
    if details:
      pron = entry.get("pronunciation")
      if pron:
        P('<div class="attr attr_pron"><span class="attr_label">発音</span>' +
          ' <span class="attr_value">{}</span></div>', pron)
      for attr_list in INFLECTIONS:
        fields = []
        for name, label in attr_list:
          value = entry.get(name)
          if value:
            value = ('<span class="attr_label">{}</span>'
                     ' <span class="attr_value">{}</span>').format(esc(label), esc(value))
            fields.append(value)
        if fields:
          P('<div class="attr attr_infl">', end="")
          print(", ".join(fields), end="")
          P('</div>')
    for num_items, item in enumerate(entry["item"]):
      if not details and num_items >= 8:
        P('<div class="item item_omit">', label)
        P('<a href="{}">... ...</a>', word_url)
        P('</div>')
        break
      label = item.get("label") or "misc"
      pos = item.get("pos") or "misc"
      pos = POSES.get(pos) or pos
      sections = item["text"].split(" [-] ")
      section = sections[0]
      attr_label = None
      attr_match = regex.search(r"^\[([a-z]+)\]: ", section)
      if attr_match:
        attr_label = WORDNET_ATTRS.get(attr_match.group(1))
        if attr_label:
          section = section[len(attr_match.group(0)):].strip()
      P('<div class="item item_{}">', label)
      P('<div class="item_text item_text1">')
      P('<span class="label">{}</span>', label.upper())
      P('<span class="pos">{}</span>', pos)
      if attr_label:
        fields = []
        bracket = ""
        bracket_match = regex.search(r"^\(.*?\)", section)
        if bracket_match:
          bracket = bracket_match.group(0)
          section = section[len(bracket):].strip()
        for subword in section.split(","):
          subword = subword.strip()
          if subword:
            subword_url = "?q={}".format(urllib.parse.quote(subword))
            fields.append('<a href="{}" class="subword">{}</a>'.format(
              esc(subword_url), esc(subword)))
        if fields:
          P('<span class="subattr_label">{}</span>', attr_label)
          P('<span class="text">', end="")
          if bracket:
            P("{} ", bracket)
          print(", ".join(fields))
          P('</span>')
      else:
        while True:
          attr_label = None
          attr_match = regex.search(r"^ *[,、]*[\(（〔]([^\)）〕]+)[\)）〕]", section)
          if not attr_match: break
          for name in regex.split(r"[ ,、]", attr_match.group(1)):
            attr_label = TEXT_ATTRS.get(name)
            if attr_label: break
          if not attr_label: break
          section = section[len(attr_match.group(0)):].strip()
          P('<span class="subattr_label">{}</span>', attr_label)
        P('<span class="text">', end="")
        print(esc(section))
        P('</span>')
      P('</div>')
      if details:
        for section in sections[1:]:
          subattr_label = None
          attr_match = regex.search(r"^\[([a-z]+)\]: ", section)
          if attr_match:
            if attr_match.group(1) == "synset": continue              
            subattr_label = WORDNET_ATTRS.get(attr_match.group(1))
            if subattr_label:
              section = section[len(attr_match.group(0)):].strip()
          subsections = section.split(" [--] ")
          P('<div class="item_text item_text2">')
          if subattr_label:
            fields = []
            for subword in subsections[0].split(","):
              subword = subword.strip()
              if subword:
                subword_url = "?q={}".format(urllib.parse.quote(subword))
                fields.append('<a href="{}" class="subword">{}</a>'.format(
                  esc(subword_url), esc(subword)))
            if fields:
              P('<span class="subattr_label">{}</span>', subattr_label)
              P('<span class="text">', end="")
              print(", ".join(fields), end="")
              P('</span>')
          else:
            P('<span class="text">{}</span>', subsections[0])
          P('</div>')
          for subsection in subsections[1:]:
            subsubsections = subsection.split(" [---] ")
            P('<div class="item_text item_text3">')
            P('<span class="text">{}</span>', subsubsections[0])
            P('</div>')
            for subsubsubsection in subsubsections[1:]:
              P('<div class="item_text item_text4">')
              P('<span class="text">{}</span>', subsubsubsection)
              P('</div>')
      P('</div>')
    if details:
      related = entry.get("related")
      if related:
        P('<div class="attr attr_related">')
        P('<span class="attr_label">関連</span>')
        P('<span class="text">')
        fields = []
        for subword in related[:8]:
          subword_url = "?q={}".format(urllib.parse.quote(subword))
          fields.append('<a href="{}" class="subword">{}</a>'.format(
            esc(subword_url), esc(subword)))
        print(", ".join(fields), end="")
        P('</span>')
        P('</div>')
      prob = entry.get("probability")
      if prob:
        P('<div class="attr attr_prob"><span class="attr_label">頻度</span>' +
          ' <span class="attr_value">{:.4f}%</span></div>', float(prob) * 100)
    P('</div>')

def PrintResultCGIList(entries, query):
  P('<div class="list">')
  for entry in entries:
    word = entry["word"]
    word_url = "?q={}".format(urllib.parse.quote(word))
    P('<div class="list_item">')
    P('<a href="{}" class="list_head">{}</a> :', word_url, word)
    translations = entry.get("translation")
    if translations:
      if tkrzw_dict.PredictLanguage(query) != "en":
        translations = tkrzw_dict.TwiddleWords(translations, query)
      fields = []
      for tran in translations[:6]:
        tran_url = "?q={}".format(urllib.parse.quote(tran))
        value = '<a href="{}" class="list_tran">{}</a>'.format(esc(tran_url), esc(tran))
        fields.append(value)
      P('<span class="list_text">', end="")
      print(", ".join(fields), end="")
      P('</span>')
    else:
      text = ""
      for item in entry["item"]:
        text = item["text"].split(" [-] ")[0]
        break
      if text:
        P('<span class="list_text"><span class="list_gross">{}</span></span>', text)
    P('</div>')
  P('</div>')


def main_cgi():
  script_name = os.environ.get("SCRIPT_NAME", sys.argv[0])
  params = {}
  form = cgi.FieldStorage()
  for key in form.keys():
    value = form[key]
    params[key] = value.value
  query = params.get("q") or ""
  search_mode = params.get("s") or "auto"
  view_mode = params.get("v") or "auto"
  print("""Content-Type: application/xhtml+xml

<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<title>Union Search Search</title>
<style type="text/css">
html {{ margin: 0ex; padding: 0ex; background: #eeeeee; }}
body {{ margin: 0ex; padding: 0ex; text-align: center; }}
article {{ display: inline-block; width: 100ex; text-align: left; padding-bottom: 3ex; }}
a,a:visited {{ text-decoration: none; }}
a:hover {{ color: #0011ee; text-decoration: underline; }}
h1 a,h2 a {{ color: #000000; text-decoration: none; }}
h1 {{ font-size: 110%; }}
h2 {{ font-size: 105%; margin: 0.7ex 0ex 0.3ex 0.8ex; }}
.search_form,.entry,.list,.note,.license {{
  border: 1px solid #dddddd; border-radius: 0.5ex;
  margin: 1ex 0ex; padding: 0.8ex 1ex 1.3ex 1ex; background: #ffffff; position: relative; }}
#query_line {{ color: #333333; }}
#query_input {{ color: #111111; width: 30ex; }}
#search_mode_box,#view_mode_box {{ color: #111111; width: 14ex; }}
#submit_button {{ color: #111111; width: 10ex; }}
.license {{ opacity: 0.7; }}
.license a {{ color: #001166; }}
.attr,.item {{ color: #999999; }}
.attr a,.item a {{ color: #111111; }}
.attr a:hover,.item a:hover {{ color: #0011ee; }}
.attr {{ margin-left: 3ex; }}
.item_text1 {{ margin-left: 3ex; }}
.item_text2 {{ margin-left: 7ex; font-size: 95%; }}
.item_text3 {{ margin-left: 10ex; font-size: 95%; }}
.item_text4 {{ margin-left: 13ex; font-size: 95%; }}
.item_omit {{ margin-left: 4ex; opacity: 0.6; font-size: 90%; }}
.attr_prob {{ margin-left: 3ex; font-size: 95%; }}
.attr_label,.label,.pos,.subattr_label {{
  display: inline-block; border: solid 1px #999999; border-radius: 0.5ex;
  font-size: 65%; min-width: 3.3ex; text-align: center; margin-right: -0.5ex;
  color: #111111; background: #eeeeee; opacity: 0.85; }}
.item_wj .label {{ background: #ddeeff; opacity: 0.7; }}
.item_we .label {{ background: #ffddee; opacity: 0.7; }}
.item_wn .label {{ background: #eeffdd; opacity: 0.7; }}
.tran {{ color: #000000; }}
.attr_value {{ margin-left: 0.3ex; color: #111111; }}
.text {{ margin-left: 0.5ex; color: #111111; }}
.list {{ padding: 1.2ex 1ex 1.5ex 1.8ex; }}
.list_item {{ margin: 0.2ex 0.3ex; color: #999999; }}
.list_head {{ font-weight: bold; color: #000000; }}
.list_head:hover {{ color: #0011ee; }}
.list_text {{ font-size: 95%; }}
.list_tran {{ color: #333333; }}
.list_tran:hover {{ color: #0011ee; }}
.list_gross {{ color: #444444; font-size: 95%; }}
</style>
<script>
function startup() {{
  let search_form = document.forms['search_form']
  if (search_form) {{
    let query_input = search_form.elements['q']
    if (query_input) {{
      query_input.focus()
    }}
  }}
}}
</script>
</head>
<body onload="startup()">
<article>
<h1><a href="{}">Union Dictionary Search</a></h1>
""".format(esc(script_name), esc(query)), end="")
  P('<div class="search_form">')
  P('<form method="get" name="search_form">')
  P('<div id="query_line">')
  P('Query: <input type="text" name="q" value="{}" id="query_input"/>', query)
  P('<select name="s" id="search_mode_box">')
  for value, label in (
      ("auto", "Auto Mode"), ("exact", "En-to-Ja"), ("reverse", "Ja-to-En"),
      ("related", "Related EJ"), ("relrev", "Related JE")):
    P('<option value="{}"', esc(value), end="")
    if value == search_mode:
      P(' selected="selected"', end="")
    P('>{}</option>', label)
  P('</select>')
  P('<select name="v" id="view_mode_box">')
  for value, label in (("auto", "Auto View"), ("full", "Full"),
                       ("simple", "Simple"), ("list", "List")):
    P('<option value="{}"', esc(value), end="")
    if value == view_mode:
      P(' selected="selected"', end="")
    P('>{}</option>', label)
  P('</select>')
  P('<input type="submit" value="search" id="submit_button"/>')
  P('</div>')
  P('</form>')
  P('</div>')
  if search_mode == "auto":
    if tkrzw_dict.PredictLanguage(query) == "en":
      search_mode = "exact"
    else:
      search_mode = "reverse"
  if query:
    searcher = tkrzw_union_searcher.UnionSearcher(CGI_DATA_PREFIX)
    if search_mode == "exact":
      result = searcher.SearchExact(query)
    elif search_mode == "reverse":
      result = searcher.SearchReverse(query)
    elif search_mode == "related":
      result = searcher.SearchRelated(query, CGI_CAPACITY)
    elif search_mode == "relrev":
      result = searcher.SearchRelatedReverse(query, CGI_CAPACITY)
    else:
      raise RuntimeError("unknown search mode: " + search_mode)
    if result:
      if view_mode == "auto":
        keys = searcher.GetResultKeys(result)
        if len(keys) < 2:
          PrintResultCGI(result, query, True)
        elif len(keys) < 6:
          PrintResultCGI(result, query, False)
        else:
          PrintResultCGIList(result, query)
      elif view_mode == "full":
        PrintResultCGI(result, query, True)
      elif view_mode == "simple":
        PrintResultCGI(result, query, False)
      elif view_mode == "list":
        PrintResultCGIList(result, query)
      else:
        raise RuntimeError("unknown view mode: " + view_mode)
    else:
      P('<div class="note">No result.</div>')
  else:
    P('<div class="license">')
    P('<p>This site demonstrats a search system on a English-Japanese dictionary.  If you input an English word, entries whose titles match it are shown.  If you input a Japanese word, entries whose translations match it are shown.</p>')
    P('<p>This service uses data from <a href="https://ja.wiktionary.org/">Japanese Wiktionary</a>, <a href="https://en.wiktionary.org/">English Wiktionary</a>, <a href="https://wordnet.princeton.edu/">WordNet</a>, and <a href="http://compling.hss.ntu.edu.sg/wnja/index.en.html">Japanese WordNet.</a></p>')
    P('<p>This service is implemented with <a href="https://dbmx.net/tkrzw/">Tkrzw</a>, which is a high performance DBM library.  <a href="https://github.com/estraier/tkrzw-dict">The code base</a> is published on GitHub.</p>')
    P('</div>')
  print("""</article>
</body>
</html>""")


if __name__=="__main__":
  interface = os.environ.get("GATEWAY_INTERFACE")
  if interface and interface.startswith("CGI/"):
    main_cgi()
  else:
    main()
