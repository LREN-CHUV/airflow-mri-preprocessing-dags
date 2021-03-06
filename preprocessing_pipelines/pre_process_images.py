"""Pre-process images (DICOM or NIFTI files) in a study folder"""

from datetime import datetime, timedelta

from airflow import DAG

from common_steps import initial_step
from common_steps.check_local_free_space import check_local_free_space_cfg
from common_steps.prepare_pipeline import prepare_pipeline
from preprocessing_steps.catalog_to_i2b2 import catalog_to_i2b2_pipeline_cfg
from preprocessing_steps.cleanup_local import cleanup_local_cfg
from preprocessing_steps.copy_to_local import copy_to_local_cfg
from preprocessing_steps.dicom_to_nifti import dicom_to_nifti_pipeline_cfg
from preprocessing_steps.features_to_i2b2 import features_to_i2b2_pipeline_cfg
from preprocessing_steps.mpm_maps import mpm_maps_pipeline_cfg
from preprocessing_steps.neuro_morphometric_atlas import neuro_morphometric_atlas_pipeline_cfg
from preprocessing_steps.notify_success import notify_success
from preprocessing_steps.register_local import register_local_cfg


shared_preparation_steps = ['copy_to_local']
dicom_preparation_steps = ['dicom_to_nitfi']
preprocessing_steps = ['mpm_maps', 'neuro_morphometric_atlas']
finalisation_steps = ['export_features', 'catalog_to_i2b2']

steps_with_file_outputs = shared_preparation_steps + dicom_preparation_steps + \
    preprocessing_steps

all_preprocessing_steps = shared_preparation_steps + dicom_preparation_steps + \
    preprocessing_steps + finalisation_steps


def pre_process_images_dag(dataset, section, email_errors_to, max_active_runs, preprocessing_pipelines=''):

    # Define the DAG

    dag_name = '%s_pre_process_images' % dataset.lower().replace(" ", "_")

    default_args = {
        'owner': 'airflow',
        'depends_on_past': False,
        'start_date': datetime.now(),
        'retries': 1,
        'retry_delay': timedelta(seconds=120),
        'email': email_errors_to,
        'email_on_failure': True,
        'email_on_retry': True
    }

    dag = DAG(
        dag_id=dag_name,
        default_args=default_args,
        schedule_interval=None,
        max_active_runs=max_active_runs)

    upstream_step = check_local_free_space_cfg(dag, initial_step, section,
                                               map(lambda p: section + ':' + p, steps_with_file_outputs))

    upstream_step = prepare_pipeline(dag, upstream_step, True)

    copy_to_local = 'copy_to_local' in preprocessing_pipelines
    dicom_to_nifti = 'dicom_to_nifti' in preprocessing_pipelines or bool(
        set(preprocessing_pipelines).intersection(set(dicom_preparation_steps)))

    if copy_to_local:
        upstream_step = copy_to_local_cfg(dag, upstream_step, section, section + ':copy_to_local')
    else:
        upstream_step = register_local_cfg(dag, upstream_step, section)
    # endif

    if dicom_to_nifti:
        upstream_step = dicom_to_nifti_pipeline_cfg(dag, upstream_step, section, section + ':dicom_to_nifti')
        if copy_to_local:
            copy_step = cleanup_local_cfg(dag, upstream_step, section + ':copy_to_local')
            upstream_step.priority_weight = copy_step.priority_weight
        # endif
    # endif

    if 'mpm_maps' in preprocessing_pipelines:
        upstream_step = mpm_maps_pipeline_cfg(dag, upstream_step, section, section + ':mpm_maps')
    # endif

    if 'neuro_morphometric_atlas' in preprocessing_pipelines:
        upstream_step = neuro_morphometric_atlas_pipeline_cfg(dag, upstream_step, section,
                                                              section + ':neuro_morphometric_atlas')
        if 'export_features' in preprocessing_pipelines:
            upstream_step = features_to_i2b2_pipeline_cfg(dag, upstream_step, 'data-factory', section)
        # endif

        if 'catalog_to_i2b2' in preprocessing_pipelines:
            upstream_step = catalog_to_i2b2_pipeline_cfg(dag, upstream_step, 'data-factory')
        # endif
    # endif

    notify_success(dag, upstream_step)

    return dag
