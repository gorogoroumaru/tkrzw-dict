#! /usr/bin/python3
# -*- coding: utf-8 -*-
#--------------------------------------------------------------------------------------------------
# Script to make an index of keywords in parallel sentences
#
# Usage:
#   index_parasentences.py [--output str] [--phrase_prob str]
#     [--keywords str] [--max_words num] [--max_ngram num] [--max_samples num]
#     [--num_buckets num] [--quiet]
#     (It reads the standard input)
#
# Example:
#   cat input.tsv | index_parasentences.py output.tkh --phrase_prob enwiki-phrase-prob.tkh
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


import collections
import logging
import math
import os
import random
import regex
import sys
import time
import tkrzw
import tkrzw_dict
import tkrzw_pron_util
import tkrzw_tokenizer


logger = tkrzw_dict.GetLogger()


class MakeIndexBatch:
  def __init__(self, output_path, phrase_prob_path, keywords_path,
               max_words, max_ngram, max_samples, num_buckets):
    self.output_path = output_path
    self.phrase_prob_path = phrase_prob_path
    self.keywords_path = keywords_path
    self.max_words = max_words
    self.max_ngram = max_ngram
    self.max_samples = max_samples
    self.num_buckets = num_buckets
    self.tokenizer = tkrzw_tokenizer.Tokenizer()
    self.output_dbm = None
    self.phrase_prob_dbm = None
    self.focus_keywords = set()
    self.word_index = {}
    self.random = random.Random(19780211)

  def Run(self):
    start_time = time.time()
    logger.info("Process started: output_path={}".format(self.output_path))
    phrase_prob_dbm = None
    if self.phrase_prob_path:
      self.phrase_prob_dbm = tkrzw.DBM()
      self.phrase_prob_dbm.Open(self.phrase_prob_path, False, dbm="HashDBM").OrDie()
    if self.keywords_path:
      self.ReadKeywords()
    self.output_dbm = tkrzw.DBM()
    self.output_dbm.Open(self.output_path, True, dbm="HashDBM",
                         truncate=True, num_buckets=self.num_buckets).OrDie()
    self.ProcessRecords()
    self.OutputIndex()
    self.output_dbm.Close().OrDie()
    if self.phrase_prob_dbm:
      self.phrase_prob_dbm.Close().OrDie()
    logger.info("Process done: elapsed_time={:.2f}s".format(time.time() - start_time))

  def ReadKeywords(self):
    start_time = time.time()
    logger.info("Reading keywords: path={}".format(self.keywords_path))
    num_lines = 0
    with open(self.keywords_path) as input_file:
      for line in input_file:
        line = line.strip()
        if not line: continue
        line = line.lower()
        self.focus_keywords.add(line)
        norm_line = " ".join(self.tokenizer.Tokenize("en", line, False, True))
        self.focus_keywords.add(norm_line)
        num_lines += 1
        if num_lines % 10000 == 0:
          logger.info("Reading keywords: lines={}".format(num_lines))
    logger.info("Reading keywords done: keywords={}, elapsed_time={:.2f}s".format(
      len(self.focus_keywords), time.time() - start_time))

  def GetPhraseProb(self, word):
    base_prob = 0.000000001
    tokens = word.split(" ")
    if not tokens: return base_prob
    max_ngram = min(3, len(tokens))
    fallback_penalty = 1.0
    for ngram in range(max_ngram, 0, -1):
      if len(tokens) <= ngram:
        cur_phrase = " ".join(tokens)
        prob = float(self.phrase_prob_dbm.GetStr(cur_phrase) or 0.0)
        if prob:
          return max(prob, base_prob)
        fallback_penalty *= 0.1
      else:
        probs = []
        index = 0
        miss = False
        while index <= len(tokens) - ngram:
          cur_phrase = " ".join(tokens[index:index + ngram])
          cur_prob = float(self.phrase_prob_dbm.GetStr(cur_phrase) or 0.0)
          if not cur_prob:
            miss = True
            break
          probs.append(cur_prob)
          index += 1
        if not miss:
          inv_sum = 0
          for cur_prob in probs:
            inv_sum += 1 / cur_prob
          prob = len(probs) / inv_sum
          prob *= 0.3 ** (len(tokens) - ngram)
          prob *= fallback_penalty
          return max(prob, base_prob)
        fallback_penalty *= 0.1
    return base_prob

  def ProcessRecords(self):
    start_time = time.time()
    logger.info("Processing records:")
    num_lines = 0
    num_words = 0
    sentence_hashes = set()
    for line in sys.stdin:
      line = line.strip()
      if not line: continue
      fields = line.split("\t")
      sentence = fields[0].strip()
      mod_sentence = sentence.lower()
      mod_sentence = regex.sub(r'[\u2018\u2019\u201C\u201D]', r'"', mod_sentence)
      mod_sentence = regex.sub(r'([-\p{Latin}0-9])"([-\p{Latin}0-9])', r'\1" \2', mod_sentence)
      sentence_hash = tkrzw.Utility.PrimaryHash(mod_sentence)
      if sentence_hash in sentence_hashes: continue
      sentence_hashes.add(sentence_hash)
      words = mod_sentence.split(" ")
      start_index = 0
      phrases = []
      uniq_phrases = set()
      while start_index < len(words):
        index = start_index
        end_index = min(start_index + self.max_ngram, len(words))
        tokens = []
        while index < end_index:
          word = words[index]
          head_symbol = False
          match = regex.search(r"^([^-\p{Latin}0-9_]+)(.*)$", word)
          if match:
            head_symbol = True
            word = match.group(2)
          tail_symbol = False
          match = regex.search(r"^(.*?)([^-\p{Latin}0-9_]+)$", word)
          if match:
            tail_symbol = True
            word = match.group(1)
          if not regex.search(r"[\p{Latin}0-9]", word): break
          num_words += 1
          if head_symbol and index > start_index: break
          tokens.append(word)
          index += 1
          phrase = " ".join(tokens)
          is_good = True
          if self.focus_keywords:
            if phrase not in self.focus_keywords:
              norm_phrase = " ".join(self.tokenizer.Tokenize("en", phrase, False, True))
              if norm_phrase not in self.focus_keywords:
                is_good = False
          if is_good and phrase not in uniq_phrases:
            phrases.append(phrase)
            uniq_phrases.add(phrase)
          if tail_symbol: break
        start_index += 1
      if len(phrases) > self.max_words:
        if self.phrase_prob_dbm:
          scored_phrases = []
          for phrase in phrases:
            prob = self.GetPhraseProb(phrase)
            scored_phrases.append((phrase, prob))
          scored_phrases = sorted(scored_phrases, key=lambda x: x[1])
          phrases = [x[0] for x in scored_phrases]
      key = "[{}]".format(num_lines)
      self.output_dbm.Set(key, line).OrDie()
      for phrase in phrases[:self.max_words]:
        old_record = self.word_index.get(phrase)
        if old_record:
          num_samples = old_record[0] + 1
          if len(old_record) <= self.max_samples:
            old_record.append(num_lines)
          else:
            rnd_value = self.random.randint(1, num_samples)
            if rnd_value < self.max_samples:
              old_record[rnd_value] = num_lines
          old_record[0] = num_samples
        else:
          self.word_index[phrase] = [1, num_lines]
      num_lines += 1
      if num_lines % 10000 == 0:
        logger.info("Processing records: lines={}".format(num_lines))    
    logger.info("Processing records done: lines={}, words={}, elapsed_time={:.2f}s".format(
      num_lines, num_words, time.time() - start_time))

  def OutputIndex(self):
    start_time = time.time()
    logger.info("Outputting index:")
    num_records = 0
    for word, ids in self.word_index.items():
      ids = sorted(ids[1:])
      value = ",".join([str(x) for x in ids])
      self.output_dbm.Set(word, value).OrDie()
      num_records += 1
      if num_records % 10000 == 0:
        logger.info("Outputting index: records={}".format(num_records))
    logger.info("Outputting index done: records={}, elapsed_time={:.2f}s".format(
      num_records, time.time() - start_time))


def main():
  args = sys.argv[1:]
  output_path = tkrzw_dict.GetCommandFlag(args, "--output", 1) or ""
  phrase_prob_path = tkrzw_dict.GetCommandFlag(args, "--phrase_prob", 1) or ""
  keywords_path = tkrzw_dict.GetCommandFlag(args, "--keywords", 1) or ""
  max_words = int(tkrzw_dict.GetCommandFlag(args, "--max_words", 1) or 50)
  max_ngram = int(tkrzw_dict.GetCommandFlag(args, "--max_ngram", 1) or 3)
  max_samples = int(tkrzw_dict.GetCommandFlag(args, "--max_samples", 1) or 100)
  num_buckets = int(tkrzw_dict.GetCommandFlag(args, "--num_buckets", 1) or 1000000)
  if tkrzw_dict.GetCommandFlag(args, "--quiet", 0):
    logger.setLevel(logging.ERROR)
  unused_flag = tkrzw_dict.GetUnusedFlag(args)
  if unused_flag:
    raise RuntimeError("Unknow flag: " + unused_flag)
  inputs = tkrzw_dict.GetArguments(args)
  if not output_path:
    raise RuntimeError("output path is required")
  MakeIndexBatch(output_path, phrase_prob_path, keywords_path,
                 max_words, max_ngram, max_samples, num_buckets).Run()


if __name__=="__main__":
  main()
