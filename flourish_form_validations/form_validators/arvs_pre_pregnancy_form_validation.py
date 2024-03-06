from django import forms
from django.apps import apps as django_apps
from django.core.exceptions import ValidationError
from edc_constants.constants import YES, NO, RESTARTED, CONTINUOUS, STOPPED, NOT_APPLICABLE
from edc_form_validators import FormValidator

from .crf_form_validator import FormValidatorMixin
from flourish_caregiver.constants import NEVER_RECEIVED_ART


class ArvsPrePregnancyFormValidator(FormValidatorMixin, FormValidator):
    caregiver_consent_model = 'flourish_caregiver.subjectconsent'
    antenatal_enrollment_model = 'flourish_caregiver.antenatalenrollment'

    @property
    def antenatal_enrollment_cls(self):
        return django_apps.get_model(self.antenatal_enrollment_model)

    @property
    def caregiver_consent_model_cls(self):
        return django_apps.get_model(self.caregiver_consent_model)

    def clean(self):
        self.subject_identifier = self.cleaned_data.get(
            'maternal_visit').subject_identifier
        super().clean()

        self.validate_prev_preg_art(cleaned_data=self.cleaned_data)
        self.validate_prior_preg(cleaned_data=self.cleaned_data)
        self.validate_maternal_consent(cleaned_data=self.cleaned_data)
        self.validate_hiv_test_date_antenatal_enrollment()
        self.validate_other_mother()

    def validate_prev_preg_art(self, cleaned_data={}):
        self.required_if(
            YES,
            field='prev_preg_art',
            field_required='art_start_date')

        art_start_date = cleaned_data.get('art_start_date')
        self.applicable_if_true(
            art_start_date is not None,
            field_applicable='is_date_estimated')

    def validate_prior_preg(self, cleaned_data=None):
        responses = (CONTINUOUS, RESTARTED)
        if (cleaned_data.get('preg_on_art') == NO
                and self.cleaned_data.get('prior_preg') in responses):
            msg = {'prior_preg': 'You indicated that the mother was NOT on'
                                 ' triple ARV when she got pregnant. Please correct.'}
            self._errors.update(msg)
            raise ValidationError(msg)

        if (cleaned_data.get('preg_on_art') == YES
                and self.cleaned_data.get('prior_preg') in [STOPPED, NOT_APPLICABLE]):
            msg = {'prior_preg': 'You indicated that the mother was still on '
                                 'triple ARV when she got pregnant, this field'
                                 ' is required.'}
            self._errors.update(msg)
            raise ValidationError(msg)

        qs = self.cleaned_data.get('prior_arv', '')
        prior_preg = self.cleaned_data.get('prior_preg', '')
        if qs and qs.count() >= 1:
            selected = {obj.short_name: obj.name for obj in qs}
            if ((prior_preg != NOT_APPLICABLE and prior_preg != NEVER_RECEIVED_ART)
                and 'prior_arv_na' in selected):
                message = {
                    'prior_arv':
                        'This field is applicable.'}
                self._errors.update(message)
                raise ValidationError(message)
            elif ((prior_preg == NOT_APPLICABLE or prior_preg == NEVER_RECEIVED_ART)
                  and 'prior_arv_na' not in selected):
                message = {
                    'prior_arv':
                        'This field is not applicable.'}
                self._errors.update(message)
                raise ValidationError(message)

    def validate_other_mother(self):
        selections = ['prior_arv_na']
        self.m2m_single_selection_if(
            *selections,
            m2m_field='prior_arv')
        self.m2m_other_specify(
            'prior_arv_specify',
            m2m_field='prior_arv',
            field_other='prior_arv_other')

    def validate_maternal_consent(self, cleaned_data=None):
        if cleaned_data.get('art_start_date'):

            if self.latest_consent_obj:

                if cleaned_data.get('art_start_date') < self.latest_consent_obj.dob:
                    msg = {'art_start_date': 'Date of triple ARVs first '
                                             'started CANNOT be before DOB.'}
                    self._errors.update(msg)
                    raise ValidationError(msg)
            else:
                raise forms.ValidationError('Maternal Consent does not exist.')

        self.applicable_if_true(
            cleaned_data.get('art_start_date') is not None,
            field_applicable='is_date_estimated')

    def validate_hiv_test_date_antenatal_enrollment(self):
        visit_instance = self.cleaned_data.get('maternal_visit', None)
        onschedule_model_cls = self.visit_onschedule_model_cls(visit_instance)
        onschedule_model_obj = self.get_onschedule_model_obj(
            self.subject_identifier, onschedule_model_cls, visit_instance.schedule_name)
        try:
            antenatal_enrollment = self.antenatal_enrollment_cls.objects.get(
                subject_identifier=self.cleaned_data.get(
                    'maternal_visit').subject_identifier,
                child_subject_identifier=self.get_child_subject_identifier(onschedule_model_obj))
        except self.antenatal_enrollment_cls.DoesNotExist:
            raise forms.ValidationError(
                'Date of HIV test required, complete Antenatal Enrollment'
                ' form before proceeding.')
        else:
            if (self.cleaned_data.get('art_start_date') and
                    self.cleaned_data.get(
                        'art_start_date') < antenatal_enrollment.week32_test_date):
                msg = {'art_start_date':
                       'ART start date cannot be before date of HIV test.'}
                self._errors.update(msg)
                raise forms.ValidationError(msg)

    @property
    def subject_screening(self):
        try:
            return self.subject_screening_cls.objects.get(
                subject_identifier=self.cleaned_data.get(
                    'maternal_visit').appointment.subject_identifier)
        except self.subject_screening_cls.DoesNotExist:
            return None
