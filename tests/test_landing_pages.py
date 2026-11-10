from django.test import TestCase
from django.urls import reverse


class LandingPageTests(TestCase):
    def test_home_renders_shared_deployment_and_github_calls_to_action(self):
        response = self.client.get(reverse('home'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'landing/index.html')
        self.assertEqual(response.context['project_name'], 'PyForge')
        self.assertContains(response, 'href="/deploy/"', count=3)
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
        self.assertContains(response, 'id="project-folder"')
        self.assertContains(response, 'id="repository-url"')
        for field_id in ('server-host', 'ssh-user', 'ssh-port', 'deploy-path'):
            with self.subTest(field=field_id):
                self.assertContains(response, f'id="{field_id}"')
        self.assertContains(response, 'type="button" disabled>Review deployment plan</button>')
        self.assertContains(response, '/static/landing/deployment_setup.js')
