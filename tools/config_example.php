<?php
	$ftpServer = 'ftp.example.com';
	$ftpUser = 'username';
	$ftpPassword = 'password';

	return array(
		array(
			'name'			 => 'My App',
			'verbose'		 => false,
			'debug'			 => false,
			'version_file'	 => 'deploy.ver',
			'git' => array(
				'root'		 => 'https://git.example.com/org/my-app.git',
				'subfolder'	 => '',
				'branch'	 => '',
				'ignore'	 => array(
					'nbproject/',
					'docs/',
					'tests/',
					'composer.json',
					'composer.lock',
					'CLAUDE.md',
					'README.md'
				),
				'username'	 => '',
				'password'	 => '',
			),
			'ftp' => array(
				'root' 		 => '/www/my-app',
				'server'	 => $ftpServer,
				'username'	 => $ftpUser,
				'password'	 => $ftpPassword,
			)
		)
	);
?>
