"""

  Pre processing step: DICOM to Nifti conversion

  Configuration variables used:

  * DATASET_CONFIG
  * PIPELINES_PATH
  * NIFTI_SPM_FUNCTION
  * NIFTI_LOCAL_FOLDER
  * NIFTI_SERVER_FOLDER
  * PROTOCOLS_FILE
  * DCM2NII_PROGRAM

"""

import os

from datetime import timedelta
from textwrap import dedent

from airflow import configuration

from airflow_spm.operators import SpmPipelineOperator

from common_steps import Step, default_config


def dicom_to_nifti_pipeline_cfg(dag, upstream_step, dataset_section):
    pipelines_path = configuration.get(dataset_section, 'PIPELINES_PATH')

    default_config(dataset_section, 'DATASET_CONFIG', '')
    default_config(dataset_section, 'NIFTI_SPM_FUNCTION', 'DCM2NII_LREN')
    default_config(dataset_section, 'DCM2NII_PROGRAM', pipelines_path + '/Nifti_Conversion_Pipeline/dcm2nii')

    dataset_config = configuration.get(dataset_section, 'DATASET_CONFIG')
    pipeline_path = pipelines_path + '/Nifti_Conversion_Pipeline'
    misc_library_path = pipelines_path + '/../Miscellaneous&Others'
    spm_function = configuration.get(dataset_section, 'NIFTI_SPM_FUNCTION')
    local_folder = configuration.get(dataset_section, 'NIFTI_LOCAL_FOLDER')
    server_folder = configuration.get(dataset_section, 'NIFTI_SERVER_FOLDER')
    protocols_file = configuration.get(dataset_section, 'PROTOCOLS_FILE')
    dcm2nii_program = configuration.get(dataset_section, 'DCM2NII_PROGRAM')

    return dicom_to_nifti_pipeline(dag, upstream_step,
                                   dataset_config=dataset_config,
                                   pipeline_path=pipeline_path,
                                   misc_library_path=misc_library_path,
                                   spm_function=spm_function,
                                   local_folder=local_folder,
                                   server_folder=server_folder,
                                   protocols_file=protocols_file,
                                   dcm2nii_program=dcm2nii_program)


def dicom_to_nifti_pipeline(dag, upstream_step,
                            dataset='',
                            dataset_config='',
                            spm_function='DCM2NII_LREN',
                            pipeline_path=None,
                            misc_library_path=None,
                            local_folder=None,
                            server_folder=None,
                            protocols_file=None,
                            dcm2nii_program=None):

    def arguments_fn(folder, session_id, **kwargs):
        """
          Prepare the arguments for conversion pipeline from DICOM to Nifti format.
          It converts all files located in the folder 'folder'
        """
        parent_data_folder = os.path.abspath(folder + '/..')

        return [parent_data_folder,
                session_id,
                local_folder,
                server_folder,
                protocols_file,
                dcm2nii_program]

    dicom_to_nifti_pipeline = SpmPipelineOperator(
        task_id='dicom_to_nifti_pipeline',
        spm_function=spm_function,
        spm_arguments_callable=arguments_fn,
        matlab_paths=[misc_library_path, pipeline_path],
        output_folder_callable=lambda session_id, **kwargs: local_folder + '/' + session_id,
        pool='io_intensive',
        parent_task=upstream_step.task_id,
        priority_weight=upstream_step.priority_weight,
        execution_timeout=timedelta(hours=24),
        on_skip_trigger_dag_id='mri_notify_skipped_processing',
        on_failure_trigger_dag_id='mri_notify_failed_processing',
        dataset_config=dataset_config,
        dag=dag
    )

    if upstream_step.task:
        dicom_to_nifti_pipeline.set_upstream(upstream_step.task)

    dicom_to_nifti_pipeline.doc_md = dedent("""\
    # DICOM to Nitfi Pipeline

    SPM function: __%s__

    This function convert the dicom files to Nifti format using the SPM tools and
    [dcm2nii](http://www.mccauslandcenter.sc.edu/mricro/mricron/dcm2nii.html) tool developed by Chris Rorden.

    Nifti files are stored the the following locations:

    * Local folder: __%s__
    * Remote folder: __%s__

    Depends on: __%s__
    """ % (spm_function, local_folder, server_folder, upstream_step.task_id))

    return Step(dicom_to_nifti_pipeline, 'dicom_to_nifti_pipeline', upstream_step.priority_weight + 10)
