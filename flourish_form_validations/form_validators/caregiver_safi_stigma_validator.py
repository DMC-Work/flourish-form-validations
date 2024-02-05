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
        fields = ['child_other_discrimination_other',
                  'child_other_discrimination_period']

        for field in fields:
            self.required_if('ever_happened',
                             field='child_other_discrimination',
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
            'child_isolated',
            'child_insulted',
            'child_home_discrimination',
            'child_neighborhood_discrimination',
            'child_religious_place_discrimination',
            'child_clinic_discrimination',
            'child_school_discrimination',
            'child_social_effect',
            'child_emotional_effect',
            'child_education_effect',
            'child_future_pespective_changed'
        ]

        for field in fields:

            self.required_if(
                'ever_happened',
                field=field,
                field_required=f'{field}_period'
            )
