import re
import apache_beam as beam
from apache_beam.options.pipeline_options import PipelineOptions, SetupOptions
from apache_beam.runners.runner import PipelineResult
from apache_beam.io import ReadFromText, WriteToText, fileio
from apache_beam.runners.direct.direct_runner import BundleBasedDirectRunner
import argparse
import logging
import time

logging.basicConfig(level=logging.INFO)


#returns ("filename.html",["link1,link2,link3, etc"])
class ExtractLinksDoFn(beam.DoFn):
        def setup(self):
            #pattern for finding files
            self.link_pattern = re.compile(r'href=["\'](.*?)["\']', re.IGNORECASE)
        def process(self, file):
            file_path = file.metadata.path
            try:
                content = file.read_utf8()
                links = self.link_pattern.findall(content)
                yield (file_path,links)
            except Exception as e:
                logging.error("Failed to process file %s: %s", file_path, str(e))
                

                
def run(argv=None, save_main_session=True):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--input',
        dest='input',
        default='gs://jasont63-nta/html-files-gcs/*.html',
        help='Input file to process.')
    parser.add_argument(
          '--output_out',
          dest='output_out',
          default="gs://jasont63-nta/outputs/out_results",
          help='Output file to write results to.')
    parser.add_argument(
          '--output_in',
          dest='output_in',
          default="gs://jasont63-nta/outputs/in_results",
          help='Output file to write results to.')
                
    known_args, pipeline_args = parser.parse_known_args(argv)
    pipeline_options = PipelineOptions(pipeline_args)
    pipeline_options.view_as(SetupOptions).save_main_session = True
    # Format the counts into a PCollection of strings.
    def format_result(filename, count):
        return '%s: %d' % (filename, count)
    with beam.Pipeline(options=pipeline_options) as p:
        # Read the text file[pattern] into a PCollection.
        extracted_links = (
            p
            | 'MatchFiles' >> fileio.MatchFiles(known_args.input)
            | 'ReadFiles' >> fileio.ReadMatches()
            | 'ExtractLinks' >> beam.ParDo(ExtractLinksDoFn())
        )   
        top_5_out = (
            extracted_links 
            |'CountOutLinks' >> beam.Map(lambda x: (x[0],len(x[1]))) #list [(filename,list [links])]-> list [(filename, len(list[link]))]
            |'GetTop5OutLink' >> beam.combiners.Top.Of(5, key=lambda x: x[1]) #[filename,len(list[link)]*5, top 5
            |'UnnestOutList' >> beam.FlatMap(lambda x: x)#[filename1,len(list[link)] ... [filename5,len(list[linkd)] not list anymore
            |'FormatOut' >> beam.MapTuple(format_result)
            |'WriteOut' >> WriteToText(known_args.output_out)
            )
        top_5_in = (
            extracted_links
            |'ExtractOnlyLinks' >> beam.FlatMap(lambda x: x[1]) #list [(filename,list [links])]-> list[links]
            |'CountInLinks' >> beam.combiners.Count.PerElement() #list[(filename,count(filename))]
            |'GetTop5InLink' >> beam.combiners.Top.Of(5, key=lambda x: x[1]) #top 5 counts
            |'UnnestInList' >> beam.FlatMap(lambda x: x)
            |'FormatIn' >> beam.MapTuple(format_result)
            |'WriteIn' >> WriteToText(known_args.output_in)
        )

if __name__ == '__main__':
    start_time = time.time()
    run()
    end_time = time.time()
    elapsed_time = end_time - start_time
    print(
      f"\n[LOCAL RUNTIME] Pipeline completed in: {elapsed_time:.2f} seconds"
      f" ({elapsed_time / 60:.2f} minutes)"
    ) 