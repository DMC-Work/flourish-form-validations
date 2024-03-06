from edc_constants.constants import YES
from edc_form_validators import FormValidator

from flourish_form_validations.form_validators.crf_form_validator import \
    FormValidatorMixin


class BriefDangerAssessmentFormValidator(FormValidatorMixin, FormValidator):

    def clean(self):
        self.required_if(
            YES,
            field='child_been_physically_hurt',
            field_required='last_time_child_hurt_datetime')

        last_time_child_hurt_datetime = self.cleaned_data.get(
            'last_time_child_hurt_datetime')

        self.required_if_true(
            last_time_child_hurt_datetime is not None,
            field_required='last_time_child_hurt_estimated',
        )
