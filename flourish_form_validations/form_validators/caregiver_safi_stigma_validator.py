from django.forms import ValidationError
from edc_constants.constants import NO, YES, OTHER
from edc_form_validators import FormValidator

from .crf_form_validator import FormValidatorMixin


class CaregiverSafiStigmaFormValidator(FormValidatorMixin, FormValidator):

    def clean(self):
        super().clean()
        self.validate_period_required()
        self.validate_other()

    def validate_other(self):
        fields = ['caregiver_other_discrimination_other',
                  'caregiver_other_discrimination_period']

        for field in fields:
            self.required_if('ever_happened',
                             field='caregiver_other_discrimination',
                             field_required=field)

    def validate_period_required(self):
        fields = [
            'judged_negatively',
            'isolated',
            'insulted',
            'discriminated_at_home',
            'discriminated_at_neigborhood',
            'discriminated_at_religious',
            'lose_finacial_support',
            'lose_social_support',
            'stressed_or_anxious',
            'depressed_or_saddened',
            'caregiver_isolated',
            'caregiver_insulted',
            'caregiver_home_discrimination',
            'caregiver_neighborhood_discrimination',
            'caregiver_religious_place_discrimination',
            'caregiver_clinic_discrimination',
            'caregiver_school_discrimination',
            'caregiver_social_effect',
            'caregiver_emotional_effect',
            'caregiver_education_effect',
            'caregiver_future_pespective_changed'
        ]

        for field in fields:

            self.required_if(
                'ever_happened',
                field=field,
                field_required=f'{field}_period'
            )
