from django.test import TestCase
from django.urls import reverse


class LandingPageTests(TestCase):
    def test_home_labels_setup_preview_and_planned_capabilities(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'landing/index.html')
        self.assertEqual(response.context['project_name'], 'PyForge')
        self.assertContains(response, 'href="/deploy/"', count=3)
        self.assertContains(response, 'Try setup demo', count=3)
        self.assertContains(response, 'Your Python app.')
        self.assertContains(response, 'Every step in view.')
        self.assertContains(response, 'PLANNED CAPABILITIES')
        self.assertContains(response, 'the current site offers an interactive setup demo, not project analysis or deployment')
        self.assertContains(response, 'Framework detection and deployment are not available yet')
        self.assertNotContains(response, 'PyForge analyzes your project, prepares a Docker deployment')
        self.assertContains(
            response,
            'href="https://github.com/whistyx1/PyForge" class="button button--secondary"',
            count=2,
        )

    def test_documentation_and_future_plans_render_their_own_pages(self):
        cases = (
            ('documentation', 'landing/documentation.html', 'Documentation'),
            ('future_plans', 'landing/future_plans.html', 'Future plans'),
        )

        for route_name, template_name, heading in cases:
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template_name)
                self.assertContains(response, heading)

    def test_deployment_setup_shows_inputs_and_disabled_review_action(self):
        response = self.client.get(reverse('deployment_setup'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'landing/deployment_setup.html')
        self.assertContains(response, 'INTERACTIVE SETUP DEMO')
        self.assertContains(response, 'does not upload your project, analyze it, connect to your server, or deploy anything')
        self.assertContains(response, 'Plan review is not available yet')
        self.assertContains(response, 'id="project-folder"')
        self.assertContains(response, 'id="repository-url"')
        for field_id in ('server-host', 'ssh-user', 'ssh-port', 'deploy-path'):
            with self.subTest(field=field_id):
                self.assertContains(response, f'id="{field_id}"')
        self.assertContains(response, 'type="button" disabled>Review deployment plan</button>')
        self.assertContains(response, '/static/landing/deployment_setup.js')

    def test_documentation_distinguishes_current_preview_from_planned_workflow(self):
        response = self.client.get(reverse('documentation'))

        self.assertContains(response, 'What works today')
        self.assertContains(response, 'It does not upload files, analyze code, check a server, create Docker configuration, or deploy an application')
        self.assertContains(response, 'Planned deployment workflow')
        self.assertNotContains(response, 'PyForge prepares a reviewable Docker deployment')

    def test_future_plans_does_not_claim_user_deployments_work_today(self):
        response = self.client.get(reverse('future_plans'))

        self.assertContains(response, 'PyForge is being built to deploy to a server you control')
        self.assertNotContains(response, 'Today, PyForge helps you deploy to a server you control')
