from django import forms
from django.apps import apps as django_apps
from django.core.exceptions import ValidationError

from edc_constants.constants import YES, NO
from edc_form_validators import FormValidator
from .crf_form_validator import FormValidatorMixin


class MaternalArvDuringPregFormValidator(FormValidatorMixin, FormValidator):

    arvs_pre_preg_model = 'flourish_caregiver.arvsprepregnancy'

    @property
    def arvs_pre_preg_cls(self):
        return django_apps.get_model(self.arvs_pre_preg_model)

    def clean(self):
        self.subject_identifier = self.cleaned_data.get(
            'maternal_visit').subject_identifier
        super().clean()

        self.applicable_if(
            YES,
            field='took_arv',
            field_applicable='is_interrupt')

        self.applicable_if(
            YES,
            field='is_interrupt',
            field_applicable='interrupt',
        )

        self.validate_other_specify(
            field='interrupt',
            other_specify_field='interrupt_other',
            required_msg='Please give reason for interruption'
        )
        
        self.validate_arv_pre_pregnancy()
        
    def validate_arv_pre_pregnancy(self, arvs_pre_preg=None):
        try:
            arvs_pre_preg = self.arvs_pre_preg_cls.objects.get(
                maternal_visit=self.cleaned_data.get('maternal_visit', None))
        except self.arvs_pre_preg_cls.DoesNotExist:
                raise forms.ValidationError(
                'Please complete the ARV\'s pre pregnancy form first.')
        else:
            if (arvs_pre_preg.preg_on_art == YES and
                    self.cleaned_data.get('took_arv') == NO):
                    message = {'took_arv':
                               'cannot be answered as No'}
                    self._errors.update(message)
                    raise ValidationError(message)    
                