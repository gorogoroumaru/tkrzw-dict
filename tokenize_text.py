#! /usr/bin/python3
# -*- coding: utf-8 -*-
#--------------------------------------------------------------------------------------------------
# Script to tokenize sentences in TSV
#
# Usage:
#   tokenize_text.py [--language str] [--lower] [--stem] [--max_sentences num] [--quiet]
#   (It reads the standard input and prints the result on the standard output.)
#
# Example:
#   $ bzcat enwiki-raw.tsv.bz2 |
#     ./tokenize_text.py --language en --lower --stem |
#     bzip2 -c > enwiki-tokenized-stem.tsv.bz2
#   $ bzcat jawiki-raw.tsv.bz2 |
#     ./tokenize_text.py --language ja --lower --stem |
#     bzip2 -c > jawiki-tokenized-stem.tsv.bz2
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

import logging
import sys
import tkrzw_dict
import tkrzw_tokenizer


logger = tkrzw_dict.GetLogger()


def ProcessTSV(tokenizer, language, lowering, stemming, max_sentences, tsv):
  num_sentences, num_words = 0, 0
  sentences = []
  for section in tsv.split("\t"):
    sentences.extend(tkrzw_tokenizer.SplitSentences(section))
  sentences = sentences[:max_sentences]
  output_fields = []
  for sentence in sentences:
    words = tokenizer.Tokenize(language, sentence, lowering, stemming)
    if words:
      output_fields.append(" ".join(words))
      num_sentences += 1
      num_words += len(words)
  if output_fields:
    print("\t".join(output_fields))
    return num_sentences, num_words
  return None


def main():
  args = sys.argv[1:]
  language = tkrzw_dict.GetCommandFlag(args, "--language", 1) or "en"
  lowering = tkrzw_dict.GetCommandFlag(args, "--lower", 0)
  stemming = tkrzw_dict.GetCommandFlag(args, "--stem", 0)
  max_sentences = int(tkrzw_dict.GetCommandFlag(args, "--max_sentences", 1) or "1000000")
  if tkrzw_dict.GetCommandFlag(args, "--quiet", 0):
    logger.setLevel(logging.ERROR)
  if args:
    raise RuntimeError("unknown arguments: {}".format(str(args)))
  logger.info("Process started: language={}, lower={}, stem={}, max_sentences_per_doc={}".format(
    language, lowering, stemming, max_sentences))
  tokenizer = tkrzw_tokenizer.Tokenizer()
  count = 0
  num_records, num_sentences, num_words = 0, 0, 0
  for line in sys.stdin:
    line = line.strip()
    if not line: continue
    count += 1
    stats = ProcessTSV(tokenizer, language, lowering, stemming, max_sentences, line)
    if stats:
      num_records += 1
      num_sentences += stats[0]
      num_words += stats[1]
    if count % 1000 == 0:
      logger.info(
        "Processing: {} input records, {} output records, {} sentences, {} words".format(
          count, num_records, num_sentences, num_words))
  logger.info(
    "Process done: {} input records, {} output records, {} sentences, {} words".format(
      count, num_records, num_sentences, num_words))


if __name__=="__main__":
  main()
