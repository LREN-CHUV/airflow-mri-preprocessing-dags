"""

  Pre processing step: copy files to local

  Configuration variables used:

  * IMAGES_SELECTION_LOCAL_FOLDER
  * IMAGES_SELECTION_CSV_PATH

"""


from datetime import timedelta
from textwrap import dedent

from airflow import configuration
from airflow_pipeline.operators import PythonPipelineOperator


def images_selection_pipeline_cfg(dag, upstream, upstream_id, priority_weight, dataset_section):
    images_selection_local_folder = configuration.get(dataset_section, 'IMAGES_SELECTION_LOCAL_FOLDER')
    images_selection_csv_path = configuration.get(dataset_section, 'IMAGES_SELECTION_CSV_PATH')

    return images_selection_pipeline(dag, upstream, upstream_id, priority_weight,
                                     images_selection_local_folder, images_selection_csv_path)


def images_selection_pipeline(dag, upstream, upstream_id, priority_weight,
                              images_selection_local_folder=None, images_selection_csv_path=None):

    def images_selection_fn(folder, session_id, **kwargs):
        """
          Selects files from DICOM/NIFTI that match criterion in CSV file.
          It selects all files located in the folder 'folder' matching criterion in CSV file
        """
        import csv
        from glob import iglob
        from os import makedirs
        from os import listdir
        from os.path import join
        from shutil import copy2

        with open(images_selection_csv_path, mode='r', newline='') as csvfile:
            filereader = csv.reader(csvfile, delimiter=',')
            for row in filereader:
                for folder in iglob(join(folder, row[0], "**/", row[1]), recursive=True):
                    path_elements = folder.split('/')
                    repetition_folder = join(images_selection_local_folder, row[0], path_elements[-3],
                                             path_elements[-2], row[1])
                    makedirs(repetition_folder, exist_ok=True)
                    for file_ in listdir(folder):
                        copy2(join(folder, file_), join(repetition_folder, file_))

        return "ok"

    images_selection_pipeline = PythonPipelineOperator(
        task_id='images_selection_pipeline',
        python_callable=images_selection_fn,
        output_folder_callable=lambda session_id, **kwargs: images_selection_local_folder + '/' + session_id,
        pool='io_intensive',
        parent_task=upstream_id,
        priority_weight=priority_weight,
        execution_timeout=timedelta(hours=6),
        on_skip_trigger_dag_id='mri_notify_skipped_processing',
        on_failure_trigger_dag_id='mri_notify_failed_processing',
        dag=dag
    )

    images_selection_pipeline.set_upstream(upstream)

    images_selection_pipeline.doc_md = dedent("""\
        # select DICOM/NIFTI pipeline

        Selects only images matching criterion defined in a CSV file from a set of various DICOM/NIFTI images. For
        example we might want to keep only the baseline visits and T1 images.

        Selected DICOM/NIFTI files are stored the the following locations:

        * Local folder: __%s__

        Depends on: __%s__
        """ % (images_selection_local_folder, upstream_id))

    upstream = images_selection_pipeline
    upstream_id = 'images_selection_pipeline'
    priority_weight += 10

    return (upstream, upstream_id, priority_weight)
