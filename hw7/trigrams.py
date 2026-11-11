import re
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, SetupOptions
from apache_beam.runners.runner import PipelineResult
from apache_beam.io import ReadFromText, WriteToText, fileio
from apache_beam.runners.direct.direct_runner import BundleBasedDirectRunner
import argparse
import logging
import time

class ExtractTrigramsDoFn(beam.DoFn):
    def setup(self):
        self.html_pattern = re.compile(r'<[^>]+>')
        
        self.word_pattern = re.compile(r'[a-z0-9]+')
    def process(self,file):
        file_path = file.metadata.path
        try:
            content = file.read_utf8()
            text_only = self.html_pattern.sub(' ', content)
            words = self.word_pattern.findall(text_only.lower())
            #for case where a file has little to no text, 
            if len(words) >= 3:
                for w1, w2, w3 in zip(words, words[1:], words[2:]):
                    yield f'{w1} {w2} {w3}'
        except Exception as e:
            logging.error('Failed to process file %s: %s', file_path, str(e))
            

def format_result(trigram, count):
    return f'{trigram}:{count}'
    
def run(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
      '--input',
      dest='input',
      default='gs://jasont63-nta/html-files-gcs/*.html',
      help='Input GCS file pattern.',
    )
    parser.add_argument(
      '--output',
      dest='output',
      default='gs://jasont63-nta/results/trigram_outputs',
      help='Output path for top 5 trigrams.',
    )
    known_args, pipeline_args = parser.parse_known_args(argv)
    pipeline_options = PipelineOptions(pipeline_args)
    pipeline_options.view_as(SetupOptions).save_main_session = True
    
    with beam.Pipeline(options=pipeline_options) as p:
        trigrams = (
            p
            | 'MatchFiles' >> fileio.MatchFiles(known_args.input)
            | 'ReadFiles' >> fileio.ReadMatches()
            | 'ExtractTrigrams' >> beam.ParDo(ExtractTrigramsDoFn())
            | 'CountTrigrams' >> beam.combiners.Count.PerElement()
            | 'GetTop5Trigrams' >> beam.combiners.Top.Of(5, key=lambda x: x[1])
            | 'UnnestList' >> beam.FlatMap(lambda x: x)#[filename1,len(list[link)] ... [filename5,len(list[linkd)] not list anymore
            | 'Format' >> beam.MapTuple(format_result)
            | 'Write' >> WriteToText(known_args.output)
            )
        
if __name__ == '__main__':
    start_time = time.time()
    run()
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(
      f"\n[RUNTIME] Pipeline completed in: {elapsed_time:.2f} seconds"
      f" ({elapsed_time / 60:.2f} minutes)"
    ) 